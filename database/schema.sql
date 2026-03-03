DROP TABLE IF EXISTS scores;
DROP TABLE IF EXISTS impact_indicators;
DROP TABLE IF EXISTS research_data;
DROP TABLE IF EXISTS faculty_profiles;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS settings;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'faculty'))
);

CREATE TABLE faculty_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    department TEXT NOT NULL,
    designation TEXT NOT NULL,
    university TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE research_data (
    id SERIAL PRIMARY KEY,
    faculty_id INTEGER NOT NULL,
    publications INTEGER DEFAULT 0,
    citations INTEGER DEFAULT 0,
    h_index INTEGER DEFAULT 0,
    i10_index INTEGER DEFAULT 0,
    FOREIGN KEY(faculty_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE impact_indicators (
    id SERIAL PRIMARY KEY,
    faculty_id INTEGER NOT NULL,
    collaboration_score FLOAT DEFAULT 0.0,
    innovation_score FLOAT DEFAULT 0.0,
    societal_impact_score FLOAT DEFAULT 0.0,
    funding_score FLOAT DEFAULT 0.0,
    patents INTEGER DEFAULT 0,
    FOREIGN KEY(faculty_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE scores (
    id SERIAL PRIMARY KEY,
    faculty_id INTEGER NOT NULL,
    total_score FLOAT DEFAULT 0.0,
    quality_score FLOAT DEFAULT 0.0,
    impact_score FLOAT DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(faculty_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE settings (
    id SERIAL PRIMARY KEY,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value FLOAT NOT NULL
);

-- Default Weights
INSERT INTO settings (setting_key, setting_value) VALUES ('weight_quality', 0.5);
INSERT INTO settings (setting_key, setting_value) VALUES ('weight_impact', 0.5);
