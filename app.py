from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import csv
import io
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_faculty_impact_key')

# Initialize Supabase client
url: str = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key: str = os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")
supabase: Client = create_client(url, key)


def recalculate_faculty_score(faculty_id):
    # Get Config
    settings_res = supabase.table("settings").select("setting_key, setting_value").execute()
    settings = {row['setting_key']: float(row['setting_value']) for row in settings_res.data}
    weight_q = settings.get('weight_quality', 0.5)
    weight_i = settings.get('weight_impact', 0.5)
    
    # Get Research Data
    rd_res = supabase.table("research_data").select("*").eq("faculty_id", faculty_id).execute()
    rd = rd_res.data[0] if rd_res.data else None
    
    # Get Impact Indicators
    ii_res = supabase.table("impact_indicators").select("*").eq("faculty_id", faculty_id).execute()
    ii = ii_res.data[0] if ii_res.data else None
    
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
        score_exists = supabase.table("scores").select("id").eq("faculty_id", faculty_id).execute()
        if score_exists.data:
            supabase.table("scores").update({
                "total_score": total_score,
                "quality_score": quality_score,
                "impact_score": impact_score
            }).eq("faculty_id", faculty_id).execute()
        else:
            supabase.table("scores").insert({
                "faculty_id": faculty_id,
                "total_score": total_score,
                "quality_score": quality_score,
                "impact_score": impact_score
            }).execute()

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
        
        user_res = supabase.table("users").select("*").eq("email", email).execute()
        user = user_res.data[0] if user_res.data else None
        
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
    # Leaderboard (Top 10 scores with user and profile info)
    # Because Supabase's python client doesn't support complex JOINs cleanly without foreign key definitions, 
    # we can fetch top scores first and then map the data.
    scores_res = supabase.table("scores").select("*").order("total_score", desc=True).limit(10).execute()
    
    leaderboard = []
    for s in scores_res.data:
        u_res = supabase.table("users").select("name").eq("id", s["faculty_id"]).execute()
        p_res = supabase.table("faculty_profiles").select("department").eq("user_id", s["faculty_id"]).execute()
        
        name = u_res.data[0]['name'] if u_res.data else "Unknown"
        dept = p_res.data[0]['department'] if p_res.data else "Unknown"
        
        leaderboard.append({
            'name': name,
            'department': dept,
            'total_score': s['total_score'],
            'quality_score': s['quality_score'],
            'impact_score': s['impact_score']
        })
    
    users_res = supabase.table("users").select("id", count="exact").eq("role", "faculty").execute()
    total_faculty = users_res.count if hasattr(users_res, 'count') else (len(users_res.data) if users_res.data else 0)
    
    depts_res = supabase.table("faculty_profiles").select("department").execute()
    total_depts = len(set(d['department'] for d in depts_res.data if 'department' in d)) if depts_res.data else 0
    
    rd_res = supabase.table("research_data").select("publications, citations").execute()
    total_pubs = sum(r['publications'] for r in rd_res.data) if rd_res.data else 0
    total_citations = sum(r['citations'] for r in rd_res.data) if rd_res.data else 0
    
    stats = {
        'total_faculty': total_faculty,
        'total_depts': total_depts,
        'total_pubs': total_pubs,
        'total_citations': total_citations
    }
    
    return render_template('admin_dashboard.html', leaderboard=leaderboard, stats=stats)

@app.route('/admin/faculty-management', methods=['GET', 'POST'])
@admin_required
def admin_faculty():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        dept = request.form['department']
        desig = request.form['designation']
        password = generate_password_hash(request.form['password'])
        
        try:
            user_res = supabase.table("users").insert({
                "name": name,
                "email": email,
                "password_hash": password,
                "role": 'faculty'
            }).execute()
            
            if not user_res.data:
                raise Exception("Failed to insert user")
                
            user_id = user_res.data[0]['id']
            
            supabase.table("faculty_profiles").insert({
                "user_id": user_id,
                "department": dept,
                "designation": desig,
                "university": 'Global University'
            }).execute()
            
            supabase.table("research_data").insert({"faculty_id": user_id}).execute()
            supabase.table("impact_indicators").insert({"faculty_id": user_id}).execute()
            
            recalculate_faculty_score(user_id)
            flash("Faculty added successfully", "success")
        except Exception as e:
            flash("Error adding faculty. Email may already be registered.", "danger")
            
    # Fetch all faculty members using Python client workaround for joins
    users_res = supabase.table("users").select("id, name, email").eq("role", "faculty").execute()
    
    faculty = []
    for u in users_res.data:
        p_res = supabase.table("faculty_profiles").select("department, designation").eq("user_id", u['id']).execute()
        dept = p_res.data[0]['department'] if p_res.data else ""
        desig = p_res.data[0]['designation'] if p_res.data else ""
        faculty.append({
            'id': u['id'],
            'name': u['name'],
            'email': u['email'],
            'department': dept,
            'designation': desig
        })
    
    depts_res = supabase.table("faculty_profiles").select("department").execute()
    depts = [{"department": d} for d in set(row['department'] for row in depts_res.data if 'department' in row)]
    
    return render_template('faculty_management.html', faculty=faculty, departments=depts)

@app.route('/admin/edit-faculty', methods=['POST'])
@admin_required
def edit_faculty():
    faculty_id = request.form['faculty_id']
    name = request.form['name']
    email = request.form['email']
    dept = request.form['department']
    desig = request.form['designation']
    
    try:
        supabase.table("users").update({"name": name, "email": email}).eq("id", faculty_id).execute()
        supabase.table("faculty_profiles").update({"department": dept, "designation": desig}).eq("user_id", faculty_id).execute()
        flash("Faculty details updated successfully", "success")
    except Exception as e:
        flash("Email already registered by another user or another error occurred", "danger")
        
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
            
            records_added = 0
            records_updated = 0
            
            for row in csv_input:
                try:
                    name = row.get('name', '').strip()
                    dept = row.get('department', '').strip()
                    desig = row.get('designation', 'Faculty') 
                    
                    pubs = int(row.get('publications', 0))
                    cites = int(row.get('citations', 0))
                    collab = float(row.get('collaboration', 0))
                    innov = float(row.get('innovation', 0))
                    patents = int(row.get('patents', 0))
                    
                    email = row.get('email', f"{name.lower().replace(' ', '.')}@university.edu")
                    
                    # Check if user already exists
                    existing_res = supabase.table("users").select("id").or_(f"name.eq.{name},email.eq.{email}").execute()
                    
                    if existing_res.data:
                        faculty_id = existing_res.data[0]['id']
                        # Update Profile
                        supabase.table("faculty_profiles").update({
                            "department": dept, "designation": desig
                        }).eq("user_id", faculty_id).execute()
                                     
                        # Update Research metrics
                        supabase.table("research_data").update({
                            "publications": pubs, "citations": cites
                        }).eq("faculty_id", faculty_id).execute()
                                     
                        # Update Impact Indicators
                        supabase.table("impact_indicators").update({
                            "collaboration_score": collab, 
                            "innovation_score": innov, 
                            "patents": patents
                        }).eq("faculty_id", faculty_id).execute()
                        
                        records_updated += 1
                        recalculate_faculty_score(faculty_id)
                    else:
                        # Insert New User
                        password = generate_password_hash('default_password')
                        user_res = supabase.table("users").insert({
                            "name": name, "email": email, "password_hash": password, "role": 'faculty'
                        }).execute()
                        faculty_id = user_res.data[0]['id']
                        
                        # Insert Profile
                        supabase.table("faculty_profiles").insert({
                            "user_id": faculty_id, "department": dept, "designation": desig, "university": 'Global University'
                        }).execute()
                        
                        # Insert Metrics
                        supabase.table("research_data").insert({
                            "faculty_id": faculty_id, "publications": pubs, "citations": cites
                        }).execute()
                        
                        supabase.table("impact_indicators").insert({
                            "faculty_id": faculty_id, "collaboration_score": collab, "innovation_score": innov, "patents": patents
                        }).execute()
                        
                        records_added += 1
                        recalculate_faculty_score(faculty_id)
                        
                except Exception as e:
                    print(f"Error processing row {row}: {e}")
                    continue
                    
            flash(f"CSV Processed: {records_added} added, {records_updated} updated.", "success")
            return redirect(url_for('admin_faculty'))
            
        else:
            flash("Invalid file format. Please upload a .csv file.", "danger")
            
    return render_template('upload_csv.html')

@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    settings_res = supabase.table("settings").select("setting_key, setting_value").execute()
    config = {row['setting_key']: float(row['setting_value']) for row in settings_res.data}
    return render_template('analytics.html', current_weights=config)

@app.route('/admin/update-weights', methods=['POST'])
@admin_required
def update_weights():
    wq = request.form.get('weight_quality', type=float)
    wi = request.form.get('weight_impact', type=float)
    
    if wq is not None and wi is not None:
        supabase.table("settings").update({"setting_value": str(wq)}).eq("setting_key", 'weight_quality').execute()
        supabase.table("settings").update({"setting_value": str(wi)}).eq("setting_key", 'weight_impact').execute()
        
        # Recalculate ALL faculty scores based on new weights
        faculty_res = supabase.table("users").select("id").eq("role", "faculty").execute()
        for f in faculty_res.data:
            recalculate_faculty_score(f['id'])
            
        flash("Scoring weights updated and scores recalculated.", "success")
    return redirect(url_for('admin_analytics'))

# --- Faculty Routes ---
@app.route('/faculty/dashboard')
@faculty_required
def faculty_dashboard():
    faculty_id = session['user_id']
    score_res = supabase.table("scores").select("*").eq("faculty_id", faculty_id).execute()
    score = score_res.data[0] if score_res.data else None
    return render_template('faculty_dashboard.html', score=score)

@app.route('/faculty/profile', methods=['GET', 'POST'])
@faculty_required
def faculty_profile():
    faculty_id = session['user_id']
    
    if request.method == 'POST':
        name = request.form['name']
        dept = request.form['department']
        desig = request.form['designation']
        
        supabase.table("users").update({"name": name}).eq("id", faculty_id).execute()
        supabase.table("faculty_profiles").update({"department": dept, "designation": desig}).eq("user_id", faculty_id).execute()
        session['name'] = name
        flash("Profile updated successfully", "success")
        
    u_res = supabase.table("users").select("name, email").eq("id", faculty_id).execute()
    p_res = supabase.table("faculty_profiles").select("department, designation, university").eq("user_id", faculty_id).execute()
    
    profile = {}
    if u_res.data and p_res.data:
        profile = {
            'name': u_res.data[0]['name'],
            'email': u_res.data[0]['email'],
            'department': p_res.data[0]['department'],
            'designation': p_res.data[0]['designation'],
            'university': p_res.data[0]['university']
        }
    
    return render_template('faculty_profile.html', profile=profile)

@app.route('/faculty/add-research', methods=['GET', 'POST'])
@faculty_required
def faculty_add_research():
    faculty_id = session['user_id']
    
    if request.method == 'POST':
        # Update Research DB
        pubs = request.form.get('publications', type=int, default=0)
        cites = request.form.get('citations', type=int, default=0)
        h = request.form.get('h_index', type=int, default=0)
        i10 = request.form.get('i10_index', type=int, default=0)
        
        supabase.table("research_data").update({
            "publications": pubs, "citations": cites, "h_index": h, "i10_index": i10
        }).eq("faculty_id", faculty_id).execute()
        
        collab = request.form.get('collaboration', type=float, default=0)
        innov = request.form.get('innovation', type=float, default=0)
        soc = request.form.get('societal', type=float, default=0)
        fund = request.form.get('funding', type=float, default=0)
        pat = request.form.get('patents', type=int, default=0)
        
        supabase.table("impact_indicators").update({
            "collaboration_score": collab, "innovation_score": innov, 
            "societal_impact_score": soc, "funding_score": fund, "patents": pat
        }).eq("faculty_id", faculty_id).execute()
        
        recalculate_faculty_score(faculty_id)
        flash("Research data updated successfully. Impact Score Recalculated!", "success")
        return redirect(url_for('faculty_add_research'))
        
    rd_res = supabase.table("research_data").select("*").eq("faculty_id", faculty_id).execute()
    ii_res = supabase.table("impact_indicators").select("*").eq("faculty_id", faculty_id).execute()
    
    rd = rd_res.data[0] if rd_res.data else None
    ii = ii_res.data[0] if ii_res.data else None
    
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
                    
                    # Update Research metrics
                    supabase.table("research_data").update({
                        "publications": pubs, "citations": cites
                    }).eq("faculty_id", faculty_id).execute()
                                 
                    # Update Impact Indicators
                    supabase.table("impact_indicators").update({
                        "collaboration_score": collab,
                        "innovation_score": innov,
                        "patents": patents
                    }).eq("faculty_id", faculty_id).execute()
                    
                    records_updated += 1
                    recalculate_faculty_score(faculty_id)
                    # Break after first row as faculty should only update their own record
                    break 
                        
                except Exception as e:
                    print(f"Error processing row {row}: {e}")
                    continue
            
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
    data = {}
    
    if session['role'] == 'admin':
        # Department wise performance
        
        # Since calculating AVG with JOINs is complex natively in the python SDK without defining an RPC/View,
        # we will fetch, group, and calculate it in Python.
        profiles_res = supabase.table("faculty_profiles").select("user_id, department").execute()
        scores_res = supabase.table("scores").select("faculty_id, total_score").execute()
        
        dept_scores = {}
        # Make a quick lookup by user_id
        prof_map = {p['user_id']: p['department'] for p in profiles_res.data}
        
        for s in scores_res.data:
            f_id = s['faculty_id']
            if f_id in prof_map:
                dept = prof_map[f_id]
                if dept not in dept_scores:
                    dept_scores[dept] = []
                dept_scores[dept].append(s['total_score'])
                
        labels = []
        scores = []
        for dept, scr_list in dept_scores.items():
            labels.append(dept)
            scores.append(sum(scr_list) / len(scr_list))
            
        data['dept_performance'] = {
            'labels': labels,
            'scores': scores
        }
        
        # Total scores distribution (top 10)
        top_scores = supabase.table("scores").select("*").order("total_score", desc=True).limit(10).execute()
        
        s_labels = []
        s_quality = []
        s_impact = []
        
        for ts in top_scores.data:
            u = supabase.table("users").select("name").eq("id", ts["faculty_id"]).execute()
            name = u.data[0]['name'] if u.data else "Unknown"
            s_labels.append(name)
            s_quality.append(ts["quality_score"])
            s_impact.append(ts["impact_score"])
            
        data['score_dist'] = {
            'labels': s_labels,
            'quality': s_quality,
            'impact': s_impact
        }
        
    elif session['role'] == 'faculty':
        faculty_id = session['user_id']
        
        # Radar Chart data
        ii_res = supabase.table("impact_indicators").select("*").eq("faculty_id", faculty_id).execute()
        if ii_res.data:
            ii = ii_res.data[0]
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
            
        rd_res = supabase.table("research_data").select("publications, citations").eq("faculty_id", faculty_id).execute()
        if rd_res.data:
            rd = rd_res.data[0]
            data['pubs_vs_cites'] = {
                'labels': ['Publications', 'Citations'],
                'values': [rd['publications'], rd['citations']]
            }
            
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
