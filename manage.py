"""Administrare utilizatori CRM (tabelul users; parola se stocheaza doar ca hash).

    python manage.py set-password <login> ["Nume complet"]   # parola se citeste de la tastatura/stdin
    python manage.py list-users
"""
import getpass
import os
import sys

import oracledb
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def connect():
    w = os.environ["WALLET_DIR"]
    return oracledb.connect(user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                            dsn=os.environ["DB_DSN"], config_dir=w, wallet_location=w,
                            wallet_password=os.environ.get("WALLET_PASSWORD"))


def set_password(login, full_name=None):
    pwd = getpass.getpass("Parola nouă: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\n")
    if len(pwd) < 8:
        sys.exit("Parola trebuie să aibă cel puțin 8 caractere.")
    h = generate_password_hash(pwd)
    with connect() as c, c.cursor() as cur:
        cur.execute("""
            MERGE INTO users u USING (SELECT :l login FROM dual) s ON (u.login = s.login)
            WHEN MATCHED THEN UPDATE SET pass_hash = :h, full_name = NVL(:n, u.full_name)
            WHEN NOT MATCHED THEN INSERT (login, pass_hash, full_name) VALUES (:l, :h, :n)""",
                    {"l": login, "h": h, "n": full_name})
        c.commit()
    print(f"Parola pentru '{login}' a fost setată (stocată ca hash).")


def list_users():
    with connect() as c, c.cursor() as cur:
        cur.execute("SELECT id, login, full_name, created_at FROM users ORDER BY id")
        for r in cur:
            print(*r, sep="\t")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "set-password":
        set_password(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) == 2 and sys.argv[1] == "list-users":
        list_users()
    else:
        sys.exit(__doc__)
