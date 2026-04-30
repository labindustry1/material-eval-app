# db_connector.py
import sqlite3

def init_db():
    """初始化材料物性数据库并写入基准数据"""
    conn = sqlite3.connect('materials.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS baseline_materials (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            density REAL,
            strength REAL,
            modulus REAL
        )
    ''')
    # 插入一些绝对精准的基准数据
    cursor.execute("INSERT OR IGNORE INTO baseline_materials (name, density, strength, modulus) VALUES ('T1000碳纤维', 1.62, 3000, 160)")
    cursor.execute("INSERT OR IGNORE INTO baseline_materials (name, density, strength, modulus) VALUES ('航空铝7075', 2.81, 572, 71.7)")
    conn.commit()
    conn.close()

def get_material_data(mat_name):
    """根据材料名称精确查询参数"""
    conn = sqlite3.connect('materials.db')
    cursor = conn.cursor()
    cursor.execute("SELECT density, strength, modulus FROM baseline_materials WHERE name=?", (mat_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"density": row[0], "strength": row[1], "modulus": row[2]}
    return None
