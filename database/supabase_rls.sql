-- Disable Row Level Security (RLS) entirely for the application tables
-- Or define policies to allow the 'anon' role (which acts as the default REST API role without auth headers)
-- to read and write to these tables.

ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE faculty_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE research_data DISABLE ROW LEVEL SECURITY;
ALTER TABLE impact_indicators DISABLE ROW LEVEL SECURITY;
ALTER TABLE scores DISABLE ROW LEVEL SECURITY;
ALTER TABLE settings DISABLE ROW LEVEL SECURITY;

-- If you prefer keeping RLS enabled but allowing public access (less secure but works with your API setup):
-- CREATE POLICY "Allow public read access" ON users FOR SELECT USING (true);
-- CREATE POLICY "Allow public insert access" ON users FOR INSERT WITH CHECK (true);
-- ...etc
