import psycopg2

conn = psycopg2.connect("postgres://postgres:qsLdbwueuhAJKIsVvhn06~77IvUMNbAz@turntable.proxy.rlwy.net:23554/railway")
cur = conn.cursor()

# Check SystemSetting table (used by refresh_llm_router_config)
print("=== SystemSetting / llm_routing_config ===")
cur.execute("""
    SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'et_system_settings')
""")
print("et_system_settings exists:", cur.fetchone()[0])

# Check what table SystemSetting maps to
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_name LIKE '%system_setting%' OR table_name LIKE '%setting%'
    ORDER BY table_name
""")
print("Setting tables:", [r[0] for r in cur.fetchall()])

# Check zairag_system_settings columns
print()
print("=== zairag_system_settings columns ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'zairag_system_settings'")
for row in cur.fetchall():
    print(" ", row[0])

# Check all rows in zairag_system_settings
print()
print("=== zairag_system_settings rows ===")
cur.execute("SELECT * FROM zairag_system_settings")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(" ", row)
else:
    print("  EMPTY - no settings stored")

# Check et_tenants to understand the tenant setup
print()
print("=== et_tenants ===")
cur.execute("SELECT id, name, status FROM et_tenants LIMIT 5")
for row in cur.fetchall():
    print(" ", row)

conn.close()
print("\nDone.")
