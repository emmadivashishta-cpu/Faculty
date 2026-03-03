import psycopg2
from psycopg2.extras import RealDictCursor
import os
from werkzeug.security import generate_password_hash

DATABASE = 'faculty_impact.db'

def init_db():
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost/faculty_impact')
    
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    with open('database/schema.sql', 'r') as f:
        with conn.cursor() as cur: cur.execute(f.read())
    
    cursor = conn.cursor()
    
    # 1. Admin User
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        ('Admin User', 'admin@university.edu', generate_password_hash('admin123'), 'admin')
    )
    
    # 2. Sample Faculty Records
    faculty_data = [
        {
            'name': 'Dr. Alice Smith', 'email': 'alice@university.edu', 'dept': 'Computer Science',
            'desig': 'Professor', 'pubs': 45, 'cites': 1200, 'h': 18, 'i10': 30,
            'collab': 8.5, 'innov': 9.0, 'soc': 7.5, 'fund': 8.0, 'patents': 3
        },
        {
            'name': 'Dr. Bob Johnson', 'email': 'bob@university.edu', 'dept': 'Physics',
            'desig': 'Associate Professor', 'pubs': 32, 'cites': 850, 'h': 14, 'i10': 20,
            'collab': 7.0, 'innov': 8.5, 'soc': 6.5, 'fund': 9.5, 'patents': 1
        },
        {
            'name': 'Dr. Carol White', 'email': 'carol@university.edu', 'dept': 'Biology',
            'desig': 'Assistant Professor', 'pubs': 15, 'cites': 300, 'h': 8, 'i10': 12,
            'collab': 9.0, 'innov': 7.0, 'soc': 8.5, 'fund': 6.0, 'patents': 0
        },
        {
            'name': 'Dr. David Brown', 'email': 'david@university.edu', 'dept': 'Computer Science',
            'desig': 'Associate Professor', 'pubs': 28, 'cites': 920, 'h': 16, 'i10': 22,
            'collab': 8.0, 'innov': 8.0, 'soc': 7.0, 'fund': 7.5, 'patents': 2
        },
        {
            'name': 'Dr. Eva Green', 'email': 'eva@university.edu', 'dept': 'Chemistry',
            'desig': 'Professor', 'pubs': 50, 'cites': 2100, 'h': 25, 'i10': 42,
            'collab': 9.5, 'innov': 9.5, 'soc': 9.0, 'fund': 10.0, 'patents': 5
        }
    ]
    
    for f in faculty_data:
        # Insert User
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
            (f['name'], f['email'], generate_password_hash('faculty123'), 'faculty')
        )
        user_id = cursor.fetchone()['id']
        
        # Insert Profile
        cursor.execute(
            "INSERT INTO faculty_profiles (user_id, department, designation, university) VALUES (%s, %s, %s, %s)",
            (user_id, f['dept'], f['desig'], 'Global University')
        )
        
        # Insert Research Data
        cursor.execute(
            "INSERT INTO research_data (faculty_id, publications, citations, h_index, i10_index) VALUES (%s, %s, %s, %s, %s)",
            (user_id, f['pubs'], f['cites'], f['h'], f['i10'])
        )
        
        # Insert Impact Indicators
        cursor.execute(
            "INSERT INTO impact_indicators (faculty_id, collaboration_score, innovation_score, societal_impact_score, funding_score, patents) VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, f['collab'], f['innov'], f['soc'], f['fund'], f['patents'])
        )
        
        # Calculate Initial Score
        # quality = citations_per_paper + h_index * 2 (simple weight)
        c_per_p = f['cites'] / f['pubs'] if f['pubs'] > 0 else 0
        quality_score = c_per_p + (f['h'] * 2)
        
        # impact = collab + innov + soc + fund + (patents * 2)
        impact_score = f['collab'] + f['innov'] + f['soc'] + f['fund'] + (f['patents'] * 2)
        
        # total = quality * 0.5 + impact * 0.5
        total_score = (quality_score * 0.5) + (impact_score * 0.5)
        
        # Insert Score
        cursor.execute(
            "INSERT INTO scores (faculty_id, total_score, quality_score, impact_score) VALUES (%s, %s, %s, %s)",
            (user_id, total_score, quality_score, impact_score)
        )
        
    conn.commit()
    conn.close()
    print("Database initialized successfully with sample data!")

if __name__ == '__main__':
    init_db()
