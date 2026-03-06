# Просто запустите этот файл один раз после того, как бот создаст базу
from database import populate_popular_data

if __name__ == "__main__":
    populate_popular_data()
    print("Готово!")