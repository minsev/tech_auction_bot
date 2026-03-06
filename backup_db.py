import shutil
import datetime
import os

DB_PATH = 'tech_auction.db'
BACKUP_DIR = 'backups'

def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f'tech_auction_{timestamp}.db')
    shutil.copy2(DB_PATH, backup_file)
    print(f'✅ Бэкап создан: {backup_file}')

if __name__ == '__main__':
    backup()