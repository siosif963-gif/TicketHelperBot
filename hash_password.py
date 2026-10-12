# bot/hash_password.py
import getpass
import hashlib


def main() -> None:
    pin = getpass.getpass("Введите PIN администратора: ")
    repeat = getpass.getpass("Повторите PIN: ")
    if not pin:
        print("PIN не может быть пустым.")
        return
    if pin != repeat:
        print("PIN-коды не совпадают.")
        return
    digest = hashlib.sha256(pin.encode("utf-8")).hexdigest()
    print("Вставьте эту строку в файл .env:")
    print(f"ADMIN_PASSWORD_HASH={digest}")


if __name__ == "__main__":
    main()
