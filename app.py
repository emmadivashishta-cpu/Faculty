from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import csv
import io

app = Flask(__name__)
app.secret_key = 'super_secret_faculty_impact_key'
DATABASE = 'faculty_impact.db'

class DBConnection:
    def __init__(self, conn):
        self.conn = conn
    def cursor(self):
        return self.conn.cursor()
    def execute(self, query, args=None):
        cur = self.conn.cursor()
        if args:
            cur.execute(query, args)
        else:
            cur.execute(query)
        return cur
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()

def get_db():
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost/faculty_impact')
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    return DBConnection(conn)

def recalculate_faculty_score(faculty_id):
    conn = get_db()
    c = conn.cursor()
    
    # Get Config
    c.execute("SELECT setting_key, setting_value FROM settings")
    settings = {row['setting_key']: row['setting_value'] for row in c.fetchall()}
    weight_q = settings.get('weight_quality', 0.5)
    weight_i = settings.get('weight_impact', 0.5)
    
    # Get Research Data
    c.execute("SELECT * FROM research_data WHERE faculty_id = %s", (faculty_id,))
    rd = c.fetchone()
    
    # Get Impact Indicators
    c.execute("SELECT * FROM impact_indicators WHERE faculty_id = %s", (faculty_id,))
    ii = c.fetchone()
    
    if rd and ii:
        pubs = rd['publications']
        cites = rd['citations']
        h_index = rd['h_index']
        
        collab = ii['collaboration_score']
        innov = ii['innovation_score']
        soc = ii['societal_impact_score']
        fund = ii['funding_score']
        patents = ii['patents']
        
        c_per_p = cites / pubs if pubs > 0 else 0
        quality_score = c_per_p + h_index
        impact_score = collab + innov + soc + fund + patents
        
        total_score = (quality_score * weight_q) + (impact_score * weight_i)
        
        # Upsert Score
        c.execute("SELECT id FROM scores WHERE faculty_id = %s", (faculty_id,))
        exists = c.fetchone()
        if exists:
            c.execute("""
                UPDATE scores 
                SET total_score=%s, quality_score=%s, impact_score=%s, last_updated=CURRENT_TIMESTAMP 
                WHERE faculty_id=%s
            """, (total_score, quality_score, impact_score, faculty_id))
        else:
            c.execute("""
                INSERT INTO scores (faculty_id, total_score, quality_score, impact_score) 
                VALUES (%s, %s, %s, %s)
            """, (faculty_id, total_score, quality_score, impact_score))
        
        conn.commit()
    conn.close()

# --- Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Admin access required", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def faculty_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'faculty':
            flash("Faculty access required", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('faculty_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Admin Routes ---
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db()
    
    # Leaderboard
    leaderboard = conn.execute("""
        SELECT u.name, p.department, s.total_score, s.quality_score, s.impact_score 
        FROM users u 
        JOIN faculty_profiles p ON u.id = p.user_id 
        JOIN scores s ON u.id = s.faculty_id 
        ORDER BY s.total_score DESC LIMIT 10
    """).fetchall()
    
    stats = conn.execute("""
        SELECT 
            (SELECT COUNT(*) FROM users WHERE role='faculty') as total_faculty,
            (SELECT COUNT(DISTINCT department) FROM faculty_profiles) as total_depts,
            (SELECT SUM(publications) FROM research_data) as total_pubs,
            (SELECT SUM(citations) FROM research_data) as total_citations
    """).fetchone()
    
    conn.close()
    return render_template('admin_dashboard.html', leaderboard=leaderboard, stats=stats)

@app.route('/admin/faculty-management', methods=['GET', 'POST'])
@admin_required
def admin_faculty():
    conn = get_db()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        dept = request.form['department']
        desig = request.form['designation']
        password = generate_password_hash(request.form['password'])
        
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'faculty') RETURNING id", 
                         (name, email, password))
            user_id = cursor.fetchone()['id']
            
            cursor.execute("INSERT INTO faculty_profiles (user_id, department, designation, university) VALUES (%s, %s, %s, 'Global University')",
                         (user_id, dept, desig))
            
            cursor.execute("INSERT INTO research_data (faculty_id) VALUES (%s)", (user_id,))
            cursor.execute("INSERT INTO impact_indicators (faculty_id) VALUES (%s)", (user_id,))
            
            conn.commit()
            recalculate_faculty_score(user_id)
            flash("Faculty added successfully", "success")
        except psycopg2.IntegrityError:
            flash("Email already registered", "danger")
            
    faculty = conn.execute("""
        SELECT u.id, u.name, u.email, p.department, p.designation 
        FROM users u JOIN faculty_profiles p ON u.id = p.user_id
    """).fetchall()
    
    depts = conn.execute("SELECT DISTINCT department FROM faculty_profiles").fetchall()
    conn.close()
    
    return render_template('faculty_management.html', faculty=faculty, departments=depts)

@app.route('/admin/edit-faculty', methods=['POST'])
@admin_required
def edit_faculty():
    conn = get_db()
    faculty_id = request.form['faculty_id']
    name = request.form['name']
    email = request.form['email']
    dept = request.form['department']
    desig = request.form['designation']
    
    try:
        conn.execute("UPDATE users SET name=%s, email=%s WHERE id=%s", (name, email, faculty_id))
        conn.execute("UPDATE faculty_profiles SET department=%s, designation=%s WHERE user_id=%s", 
                     (dept, desig, faculty_id))
        conn.commit()
        flash("Faculty details updated successfully", "success")
    except psycopg2.IntegrityError:
        flash("Email already registered by another user", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('admin_faculty'))

@app.route('/admin/upload-csv', methods=['GET', 'POST'])
@admin_required
def upload_csv():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['csv_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and file.filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            conn = get_db()
            records_added = 0
            records_updated = 0
            
            for row in csv_input:
                try:
                    name = row.get('name', '').strip()
                    dept = row.get('department', '').strip()
                    # If designation is not present, use a default
                    desig = row.get('designation', 'Faculty') 
                    
                    pubs = int(row.get('publications', 0))
                    cites = int(row.get('citations', 0))
                    collab = float(row.get('collaboration', 0))
                    innov = float(row.get('innovation', 0))
                    patents = int(row.get('patents', 0)) # New field based on user request
                    
                    # Generate a dummy email if not provided
                    email = row.get('email', f"{name.lower().replace(' ', '.')}@university.edu")
                    
                    cursor = conn.cursor()
                    
                    # Check if user already exists (by name or email)
                    existing = cursor.execute("SELECT id FROM users WHERE name = %s OR email = %s", (name, email)).fetchone()
                    
                    if existing:
                        faculty_id = existing['id']
                        # Update Profile
                        cursor.execute("UPDATE faculty_profiles SET department=%s, designation=%s WHERE user_id=%s", 
                                     (dept, desig, faculty_id))
                                     
                        # Update Research metrics
                        cursor.execute("UPDATE research_data SET publications=%s, citations=%s WHERE faculty_id=%s",
                                     (pubs, cites, faculty_id))
                                     
                        # Update Impact Indicators
                        cursor.execute("""
                            UPDATE impact_indicators 
                            SET collaboration_score=%s, innovation_score=%s, patents=%s
                            WHERE faculty_id=%s
                        """, (collab, innov, patents, faculty_id))
                        
                        records_updated += 1
                        recalculate_faculty_score(faculty_id)
                    else:
                        # Insert New User
                        password = generate_password_hash('default_password')
                        cursor.execute("INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'faculty') RETURNING id", 
                                     (name, email, password))
                        faculty_id = cursor.fetchone()['id']
                        
                        # Insert Profile
                        cursor.execute("INSERT INTO faculty_profiles (user_id, department, designation, university) VALUES (%s, %s, %s, 'Global University')",
                                     (faculty_id, dept, desig))
                        
                        # Insert Metrics
                        cursor.execute("INSERT INTO research_data (faculty_id, publications, citations) VALUES (%s, %s, %s)",
                                     (faculty_id, pubs, cites))
                        
                        cursor.execute("INSERT INTO impact_indicators (faculty_id, collaboration_score, innovation_score, patents) VALUES (%s, %s, %s, %s)",
                                     (faculty_id, collab, innov, patents))
                        
                        records_added += 1
                        recalculate_faculty_score(faculty_id)
                        
                except Exception as e:
                    print(f"Error processing row {row}: {e}")
                    continue
                    
            conn.commit()
            conn.close()
            flash(f"CSV Processed: {records_added} added, {records_updated} updated.", "success")
            return redirect(url_for('admin_faculty'))
            
        else:
            flash("Invalid file format. Please upload a .csv file.", "danger")
            
    return render_template('upload_csv.html')

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    conn = get_db()
    settings = conn.execute("SELECT setting_key, setting_value FROM settings").fetchall()
    config = {row['setting_key']: row['setting_value'] for row in settings}
    conn.close()
    return render_template('analytics.html', current_weights=config)

@app.route('/admin/update-weights', methods=['POST'])
@admin_required
def update_weights():
    wq = request.form.get('weight_quality', type=float)
    wi = request.form.get('weight_impact', type=float)
    
    if wq is not None and wi is not None:
        conn = get_db()
        conn.execute("UPDATE settings SET setting_value=%s WHERE setting_key='weight_quality'", (wq,))
        conn.execute("UPDATE settings SET setting_value=%s WHERE setting_key='weight_impact'", (wi,))
        conn.commit()
        
        # Recalculate ALL faculty scores based on new weights
        faculty = conn.execute("SELECT id FROM users WHERE role='faculty'").fetchall()
        for f in faculty:
            recalculate_faculty_score(f['id'])
            
        conn.close()
        flash("Scoring weights updated and scores recalculated.", "success")
    return redirect(url_for('admin_analytics'))

# --- Faculty Routes ---
@app.route('/faculty/dashboard')
@faculty_required
def faculty_dashboard():
    conn = get_db()
    faculty_id = session['user_id']
    score = conn.execute("SELECT * FROM scores WHERE faculty_id=%s", (faculty_id,)).fetchone()
    conn.close()
    return render_template('faculty_dashboard.html', score=score)

@app.route('/faculty/profile', methods=['GET', 'POST'])
@faculty_required
def faculty_profile():
    conn = get_db()
    faculty_id = session['user_id']
    
    if request.method == 'POST':
        name = request.form['name']
        dept = request.form['department']
        desig = request.form['designation']
        
        conn.execute("UPDATE users SET name=%s WHERE id=%s", (name, faculty_id))
        conn.execute("UPDATE faculty_profiles SET department=%s, designation=%s WHERE user_id=%s", 
                     (dept, desig, faculty_id))
        conn.commit()
        session['name'] = name
        flash("Profile updated successfully", "success")
        
    profile = conn.execute("""
        SELECT u.name, u.email, p.department, p.designation, p.university 
        FROM users u JOIN faculty_profiles p ON u.id = p.user_id 
        WHERE u.id = %s
    """, (faculty_id,)).fetchone()
    conn.close()
    
    return render_template('faculty_profile.html', profile=profile)

@app.route('/faculty/add-research', methods=['GET', 'POST'])
@faculty_required
def faculty_add_research():
    conn = get_db()
    faculty_id = session['user_id']
    
    if request.method == 'POST':
        # Update Research DB
        pubs = request.form.get('publications', type=int, default=0)
        cites = request.form.get('citations', type=int, default=0)
        h = request.form.get('h_index', type=int, default=0)
        i10 = request.form.get('i10_index', type=int, default=0)
        
        conn.execute("""
            UPDATE research_data 
            SET publications=%s, citations=%s, h_index=%s, i10_index=%s 
            WHERE faculty_id=%s
        """, (pubs, cites, h, i10, faculty_id))
        
        collab = request.form.get('collaboration', type=float, default=0)
        innov = request.form.get('innovation', type=float, default=0)
        soc = request.form.get('societal', type=float, default=0)
        fund = request.form.get('funding', type=float, default=0)
        pat = request.form.get('patents', type=int, default=0)
        
        conn.execute("""
            UPDATE impact_indicators 
            SET collaboration_score=%s, innovation_score=%s, societal_impact_score=%s, funding_score=%s, patents=%s 
            WHERE faculty_id=%s
        """, (collab, innov, soc, fund, pat, faculty_id))
        
        conn.commit()
        conn.close()
        
        recalculate_faculty_score(faculty_id)
        flash("Research data updated successfully. Impact Score Recalculated!", "success")
        return redirect(url_for('faculty_add_research'))
        
    rd = conn.execute("SELECT * FROM research_data WHERE faculty_id=%s", (faculty_id,)).fetchone()
    ii = conn.execute("SELECT * FROM impact_indicators WHERE faculty_id=%s", (faculty_id,)).fetchone()
    conn.close()
    
    return render_template('add_research.html', rd=rd, ii=ii)

@app.route('/faculty/upload-csv', methods=['GET', 'POST'])
@faculty_required
def faculty_upload_csv():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['csv_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and file.filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            conn = get_db()
            records_updated = 0
            faculty_id = session['user_id']
            # We only process the first row for faculty members to update their own data
            
            for row in csv_input:
                try:
                    pubs = int(row.get('publications', 0))
                    cites = int(row.get('citations', 0))
                    collab = float(row.get('collaboration', 0))
                    innov = float(row.get('innovation', 0))
                    patents = int(row.get('patents', 0))
                    
                    cursor = conn.cursor()
                    # Update Research metrics
                    cursor.execute("UPDATE research_data SET publications=%s, citations=%s WHERE faculty_id=%s",
                                 (pubs, cites, faculty_id))
                                 
                    # Update Impact Indicators
                    cursor.execute("""
                        UPDATE impact_indicators 
                        SET collaboration_score=%s, innovation_score=%s, patents=%s
                        WHERE faculty_id=%s
                    """, (collab, innov, patents, faculty_id))
                    
                    records_updated += 1
                    recalculate_faculty_score(faculty_id)
                    # Break after first row as faculty should only update their own record
                    break 
                        
                except Exception as e:
                    print(f"Error processing row {row}: {e}")
                    continue
                    
            conn.commit()
            conn.close()
            
            if records_updated > 0:
                flash("Research data updated successfully from CSV. Impact Score Recalculated!", "success")
            else:
                flash("Failed to read CSV data. Please check the format.", "warning")
                
            return redirect(url_for('faculty_add_research'))
            
        else:
            flash("Invalid file format. Please upload a .csv file.", "danger")
            
    return render_template('upload_csv_faculty.html')

# --- API Endpoints ---
@app.route('/api/charts')
@login_required
def api_charts():
    conn = get_db()
    data = {}
    
    if session['role'] == 'admin':
        # Department wise performance
        dept_perf = conn.execute("""
            SELECT p.department, AVG(s.total_score) as avg_score 
            FROM faculty_profiles p 
            JOIN scores s ON p.user_id = s.faculty_id 
            GROUP BY p.department
        """).fetchall()
        data['dept_performance'] = {
            'labels': [row['department'] for row in dept_perf],
            'scores': [row['avg_score'] for row in dept_perf]
        }
        
        # Total scores distribution (top 10)
        dist = conn.execute("""
            SELECT u.name, s.quality_score, s.impact_score 
            FROM scores s JOIN users u ON s.faculty_id = u.id
            ORDER BY s.total_score DESC LIMIT 10
        """).fetchall()
        data['score_dist'] = {
            'labels': [row['name'] for row in dist],
            'quality': [row['quality_score'] for row in dist],
            'impact': [row['impact_score'] for row in dist]
        }
        
    elif session['role'] == 'faculty':
        faculty_id = session['user_id']
        
        # Radar Chart data
        ii = conn.execute("SELECT * FROM impact_indicators WHERE faculty_id=%s", (faculty_id,)).fetchone()
        if ii:
            data['radar'] = {
                'labels': ['Collaboration', 'Innovation', 'Societal Impact', 'Funding', 'Patents'],
                'values': [
                    ii['collaboration_score'], 
                    ii['innovation_score'], 
                    ii['societal_impact_score'], 
                    ii['funding_score'], 
                    ii['patents']
                ]
            }
            
        rd = conn.execute("SELECT publications, citations FROM research_data WHERE faculty_id=%s", (faculty_id,)).fetchone()
        if rd:
            data['pubs_vs_cites'] = {
                'labels': ['Publications', 'Citations'],
                'values': [rd['publications'], rd['citations']]
            }
            
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
