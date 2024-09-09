# class DB:

#     def __init__(self, db):
#         self.db = db
#         self.conn = sqlite3.connect(self.db)
#         self.cursor = self.conn.cursor()

#     def close(self):
#         self.conn.commit()
#         self.conn.close()