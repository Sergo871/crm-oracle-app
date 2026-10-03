"""Demo CRM peste schema Oracle CRM_DEMO — Flask + python-oracledb."""
import calendar as _calendar
import datetime as dt
import os
import secrets
import time
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import oracledb  # noqa: E402
from flask import (Flask, abort, flash, jsonify, redirect, render_template,  # noqa: E402
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

import db  # noqa: E402
from schema import CHOICES, KANBAN, LOOKUPS, NAV, RO, STAGE_COLORS, TABLES  # noqa: E402

app = Flask(__name__)
# nginx: location /crm/ -> proxy_pass http://127.0.0.1:5002/ + X-Forwarded-Prefix /crm
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config.update(
    SECRET_KEY=os.environ["SECRET_KEY"],
    SESSION_COOKIE_NAME="crm_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "1") == "1",
    PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=12),
)
app.teardown_appcontext(db.close)

PER_PAGE = 20
KANBAN_PER_COLUMN = 50
MONTHS = ["", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie", "Iulie",
          "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie"]
WEEKDAYS = ["Lu", "Ma", "Mi", "Jo", "Vi", "Sâ", "Du"]


# ---------------------------------------------------------------- filtre Jinja

def ro(v):
    return RO.get(v, v) if v is not None else ""


def money(v):
    if v is None or v == "":
        return ""
    s = f"{Decimal(v):,.2f}"
    return s.replace(",", " ").replace(".", ",")


def num(v):
    if v is None or v == "":
        return ""
    d = Decimal(v)
    s = f"{d:,.3f}".rstrip("0").rstrip(".")
    return s.replace(",", " ").replace(".", ",")


def fdate(v):
    return v.strftime("%d.%m.%Y") if v else ""


def fdatetime(v):
    return v.strftime("%d.%m.%Y %H:%M") if v else ""


app.jinja_env.filters.update(ro=ro, money=money, num=num, fdate=fdate, fdatetime=fdatetime)


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def url_with(**kw):
    """URL-ul paginii curente cu argumentele GET modificate (None = sters)."""
    args = request.args.to_dict()
    args.update(request.view_args or {})
    for k, v in kw.items():
        if v is None:
            args.pop(k, None)
        else:
            args[k] = v
    return url_for(request.endpoint, **args)


def view_args():
    """Argumentele GET pastrate la comutarea Lista/Kanban (cautarea si filtrele)."""
    return {k: v for k, v in request.args.items() if k not in ("page", "sort", "dir")}


def nav_url(key):
    if key in ("dashboard", "calendar"):
        return url_for(key)
    if key in KANBAN and session.get("views", {}).get(key) == "kanban":
        return url_for("table_kanban", table=key)
    return url_for("table_list", table=key)


def remember_view(table, view):
    """Meniul lateral deschide ultima vedere aleasa (Lista/Kanban) pentru fiecare tabel."""
    views = session.get("views", {})
    if views.get(table) != view:
        session["views"] = dict(views, **{table: view})


def stage_color(choices, v):
    return STAGE_COLORS.get(choices, {}).get(v, "")


def nav_badges():
    """Contoare in meniul lateral (ca in Bitrix24): sarcini intarziate."""
    try:
        late = db.scalar("SELECT COUNT(*) FROM tasks"
                         " WHERE NVL(done,0) = 0 AND due_at < TRUNC(SYSDATE)")
    except oracledb.DatabaseError:
        return {}
    return {"tasks": late} if late else {}


def initials(name):
    parts = (name or "?").split()
    return "".join(p[0] for p in parts[:2]).upper()


app.jinja_env.globals.update(csrf_token=csrf_token, url_with=url_with, nav_url=nav_url,
                             view_args=view_args, nav_badges=nav_badges,
                             stage_color=stage_color, initials=initials, NAV=NAV,
                             CHOICES=CHOICES, TABLES=TABLES, KANBAN=KANBAN)


@app.context_processor
def active_section():
    va = request.view_args or {}
    active = va.get("table") or {"order_detail": "orders", "calendar": "calendar",
                                 "dashboard": "dashboard"}.get(request.endpoint)
    return {"active": active, "today": dt.date.today()}


# ---------------------------------------------------------------- autentificare

PUBLIC = {"login", "static"}


@app.before_request
def guard():
    # cererile fetch() (mutarea cardurilor Kanban) primesc erorile ca JSON
    is_fetch = request.headers.get("X-Requested-With") == "fetch"
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            msg = "Token CSRF invalid — reîncărcați pagina."
            if is_fetch:
                return jsonify(ok=False, error=msg), 400
            abort(400, msg)
    if request.endpoint in PUBLIC or request.endpoint is None:
        return None
    if not session.get("uid"):
        if is_fetch:
            return jsonify(ok=False, error="Sesiunea a expirat — autentificați-vă din nou."), 401
        return redirect(url_for("login", next=request.full_path))
    return None


def safe_next(nxt):
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return request.script_root + nxt
    return url_for("dashboard")


# Cont demonstrativ: formularul de logare vine precompletat, se apasă doar „Intră”.
# Se dezactivează cu DEMO_LOGIN= (gol) în .env.
DEMO_LOGIN = os.environ.get("DEMO_LOGIN", "DEMO").strip()
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "DEMO123")
_demo_ready = False


def ensure_demo_user():
    """Creează/actualizează utilizatorul DEMO în tabelul users (parola doar ca hash)."""
    global _demo_ready
    if _demo_ready or not DEMO_LOGIN:
        return
    u = db.one("SELECT pass_hash FROM users WHERE login = :l", {"l": DEMO_LOGIN})
    if not u or not check_password_hash(u["pass_hash"], DEMO_PASSWORD):
        db.execute("""
            MERGE INTO users u USING (SELECT :l login FROM dual) s ON (u.login = s.login)
            WHEN MATCHED THEN UPDATE SET pass_hash = :h
            WHEN NOT MATCHED THEN INSERT (login, pass_hash, full_name) VALUES (:l, :h, 'Demo')""",
                   {"l": DEMO_LOGIN, "h": generate_password_hash(DEMO_PASSWORD)})
        db.commit()
    _demo_ready = True


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    ensure_demo_user()
    if request.method == "POST":
        login_ = request.form.get("login", "").strip()
        pwd = request.form.get("password", "")
        u = db.one("SELECT id, login, pass_hash, full_name FROM users WHERE login = :l",
                   {"l": login_})
        if u and check_password_hash(u["pass_hash"], pwd):
            nxt = request.args.get("next")
            session.clear()
            session.permanent = True
            session.update(uid=u["id"], name=u["full_name"] or u["login"])
            return redirect(safe_next(nxt))
        time.sleep(1)
        error = "Utilizator sau parolă greșită."
    return render_template("login.html", error=error,
                           demo_login=DEMO_LOGIN, demo_password=DEMO_PASSWORD)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- panou

@app.route("/")
def dashboard():
    def by_order(rows, key, order):
        idx = {v: i for i, v in enumerate(order)}
        return sorted(rows, key=lambda r: idx.get(r[key], 99))

    stages = by_order(db.query(
        "SELECT stage, COUNT(*) n, NVL(SUM(amount),0) s FROM deals GROUP BY stage"),
        "stage", CHOICES["deal_stage"])
    statuses = by_order(db.query(
        "SELECT status, COUNT(*) n, NVL(SUM(total),0) s FROM orders GROUP BY status"),
        "status", CHOICES["order_status"])
    open_tasks = db.query("""
        SELECT t.id, t.subject, t.due_at, t.priority, t.assignee,
               (SELECT c.denumire FROM clients c WHERE c.id = t.client_id) client
          FROM tasks t WHERE NVL(t.done,0) = 0
         ORDER BY t.due_at NULLS LAST, t.id FETCH FIRST 8 ROWS ONLY""")
    top = db.query("""
        SELECT c.id, c.denumire, COUNT(o.id) n, NVL(SUM(o.total),0) s
          FROM clients c JOIN orders o ON o.client_id = c.id
         WHERE NVL(o.status,'-') <> 'Отменён'
         GROUP BY c.id, c.denumire ORDER BY s DESC FETCH FIRST 5 ROWS ONLY""")
    kpi = db.one("""
        SELECT (SELECT COUNT(*) FROM clients) clients,
               (SELECT COUNT(*) FROM deals WHERE stage NOT IN ('Выиграна','Проиграна')) deals_n,
               (SELECT NVL(SUM(amount),0) FROM deals
                 WHERE stage NOT IN ('Выиграна','Проиграна')) deals_s,
               (SELECT NVL(SUM(amount),0) FROM deals WHERE stage = 'Выиграна') won_s,
               (SELECT COUNT(*) FROM orders
                 WHERE status NOT IN ('Выполнен','Оплачен','Отменён')) orders_open,
               (SELECT COUNT(*) FROM tasks WHERE NVL(done,0) = 0) tasks_open,
               (SELECT COUNT(*) FROM tasks
                 WHERE NVL(done,0) = 0 AND due_at < TRUNC(SYSDATE)) tasks_late
          FROM dual""")
    max_stage = max([r["s"] for r in stages] + [1])
    max_status = max([r["s"] for r in statuses] + [1])
    max_top = max([r["s"] for r in top] + [1])
    return render_template("dashboard.html", stages=stages, statuses=statuses,
                           open_tasks=open_tasks, top=top, kpi=kpi, max_stage=max_stage,
                           max_status=max_status, max_top=max_top)


# ---------------------------------------------------------------- liste generice

def get_table(table):
    T = TABLES.get(table)
    if not T:
        abort(404)
    return T


def like_escape(s):
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def inner_select(T):
    cols = ["t.*"]
    for f in T["fields"]:
        if f["type"] == "fk":
            ref = f["ref"]
            cols.append(f"(SELECT x.{LOOKUPS[ref]} FROM {ref} x WHERE x.id = t.{f['name']})"
                        f" AS {f['name']}__lbl")
    return f"SELECT {', '.join(cols)} FROM {T['table']} t"


def fk_label(ref, rid):
    if rid is None:
        return None
    return db.scalar(f"SELECT {LOOKUPS[ref]} FROM {ref} WHERE id = :i", {"i": rid})


def build_filters(T, args, q):
    """Conditiile WHERE pentru cautarea q si filtrele din args (liste, Kanban, cautare)."""
    where, binds, chips = [], {}, []
    if q:
        binds["q"] = "%" + like_escape(q.upper()) + "%"
        ors = []
        for f in T["fields"]:
            if not f.get("search"):
                continue
            if f["type"] == "fk":
                ors.append(f"UPPER({f['name']}__lbl) LIKE :q ESCAPE '\\'")
            elif f["type"] == "choice":
                hits = [v for v in CHOICES[f["choices"]]
                        if q.lower() in v.lower() or q.lower() in ro(v).lower()]
                names = []
                for i, v in enumerate(hits):
                    binds[f"c_{f['name']}_{i}"] = v
                    names.append(f":c_{f['name']}_{i}")
                if names:
                    ors.append(f"{f['name']} IN ({', '.join(names)})")
            else:
                ors.append(f"UPPER({f['name']}) LIKE :q ESCAPE '\\'")
        where.append("(" + (" OR ".join(ors) or "1 = 0") + ")")

    for f in T["fields"]:
        v = args.get(f["name"], "")
        if v == "":
            continue
        if f["type"] == "fk" and v.isdigit():
            where.append(f"{f['name']} = :f_{f['name']}")
            binds[f"f_{f['name']}"] = int(v)
            chips.append((f, fk_label(f["ref"], int(v)) or v))
        elif f["type"] == "choice" and f["name"] in T["filters"]:
            where.append(f"{f['name']} = :f_{f['name']}")
            binds[f"f_{f['name']}"] = v
        elif f["type"] == "bool" and v in ("0", "1"):
            where.append(f"NVL({f['name']},0) = :f_{f['name']}")
            binds[f"f_{f['name']}"] = int(v)
    return where, binds, chips


def filtered_base(T, where):
    base = f"SELECT * FROM ({inner_select(T)})"
    if where:
        base += " WHERE " + " AND ".join(where)
    return base


def row_href(table, T, r):
    if table == "orders":
        return url_for("order_detail", oid=r["id"])
    return url_for("table_form", table=table, pk=r[T["pk"]])


@app.route("/<table>/")
def table_list(table):
    T = get_table(table)
    if table in KANBAN:
        remember_view(table, "list")
    q = request.args.get("q", "").strip()
    where, binds, chips = build_filters(T, request.args, q)

    cols = [f for f in T["fields"] if f.get("list")]
    sort = request.args.get("sort", T["sort"][0])
    if sort not in [f["name"] for f in cols]:
        sort = T["sort"][0]
    direction = request.args.get("dir", T["sort"][1] if sort == T["sort"][0] else "asc")
    direction = "desc" if direction == "desc" else "asc"
    sort_expr = sort + "__lbl" if T["by_name"][sort]["type"] == "fk" else sort
    if T["by_name"][sort]["type"] in ("text", "tel", "email", "fk"):
        sort_expr = f"NLSSORT({sort_expr}, 'NLS_SORT=GENERIC_M_CI')"

    base = filtered_base(T, where)
    total = db.scalar(f"SELECT COUNT(*) FROM ({base})", binds)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    try:
        page = min(max(1, int(request.args.get("page", 1))), pages)
    except ValueError:
        page = 1
    rows = db.query(
        f"{base} ORDER BY {sort_expr} {direction} NULLS LAST, {T['pk']}"
        f" OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY",
        dict(binds, off=(page - 1) * PER_PAGE, lim=PER_PAGE))
    return render_template("list.html", T=T, table=table, cols=cols, rows=rows, q=q,
                           total=total, page=page, pages=pages, sort=sort,
                           direction=direction, chips=chips,
                           filtered=bool(q or chips or any(request.args.get(n) for n in T["filters"])),
                           prefill={f["name"]: request.args[f["name"]] for f, _ in chips})


# ---------------------------------------------------------------- formulare generice

def to_input(f, v):
    """Valoare din baza -> text pentru <input>."""
    if v is None:
        return ""
    t = f["type"]
    if t == "date":
        return v.strftime("%Y-%m-%d")
    if t == "datetime":
        return fdatetime(v)
    if t in ("num", "money", "int"):
        s = format(Decimal(v), "f")
        return s.rstrip("0").rstrip(".") if "." in s else s
    if t in ("bool", "fk"):
        return str(int(v))
    return str(v)


def parse_value(f, raw):
    t = f["type"]
    raw = (raw or "").strip()
    if t == "bool":
        return (1 if raw in ("1", "on") else 0), None
    if raw == "":
        return None, ("Câmp obligatoriu." if f.get("req") else None)
    if t in ("int", "fk"):
        try:
            return int(raw), None
        except ValueError:
            return None, "Număr întreg invalid."
    if t in ("num", "money"):
        try:
            return Decimal(raw.replace(" ", "").replace(",", ".")), None
        except InvalidOperation:
            return None, "Număr invalid."
    if t == "date":
        try:
            return dt.datetime.strptime(raw, "%Y-%m-%d"), None
        except ValueError:
            return None, "Dată invalidă."
    if t == "email" and "@" not in raw:
        return raw, "Adresă de e-mail invalidă."
    return raw, None


def editable(T):
    return [f for f in T["fields"] if not f.get("ro")]


def parse_form(T, form):
    vals, errors = {}, {}
    for f in editable(T):
        v, err = parse_value(f, form.get(f["name"]))
        vals[f["name"]] = v
        if err:
            errors[f["name"]] = err
    return vals, errors


def default_inputs(T):
    out = {}
    for f in T["fields"]:
        d = request.args.get(f["name"], f.get("default"))
        if d == "today":
            d = dt.date.today().strftime("%Y-%m-%d")
        out[f["name"]] = "" if d is None else str(d)
    return out


def fk_options(T):
    opts = {}
    for f in T["fields"]:
        if f["type"] == "fk":
            ref = f["ref"]
            opts[f["name"]] = db.query(
                f"SELECT id, {LOOKUPS[ref]} lbl FROM {ref} ORDER BY NLSSORT({LOOKUPS[ref]},"
                f" 'NLS_SORT=GENERIC_M_CI')")
    return opts


def suggestions(T):
    sug = {}
    for f in T["fields"]:
        if f.get("suggest"):
            sug[f["name"]] = [r["v"] for r in db.query(
                f"SELECT DISTINCT {f['name']} v FROM {T['table']}"
                f" WHERE {f['name']} IS NOT NULL ORDER BY 1")]
    return sug


def db_error(e):
    msg = str(e)
    if "ORA-02292" in msg:
        return "Nu se poate șterge: există înregistrări legate de aceasta."
    if "ORA-00001" in msg:
        return "Există deja o înregistrare cu această valoare unică (ex. IDNO)."
    if "ORA-12899" in msg:
        return "Un text este prea lung pentru câmpul respectiv."
    if "ORA-01400" in msg:
        return "Lipsește o valoare obligatorie."
    if "ORA-02291" in msg:
        return "Legătura aleasă nu mai există."
    return "Eroare la baza de date: " + msg.split("\n")[0]


def before_save(table, vals, is_new):
    if table == "companies":
        vals["updated_at"] = dt.datetime.now()
        if is_new:
            vals["company_key"] = vals.get("idno")


def insert_row(T, vals):
    cols = list(vals)
    with db.conn().cursor() as cur:
        rid = cur.var(int if T["pk_int"] else str)
        cur.execute(
            f"INSERT INTO {T['table']} ({', '.join(cols)}) VALUES "
            f"({', '.join(':v_' + c for c in cols)}) RETURNING {T['pk']} INTO :rid",
            dict({"v_" + c: vals[c] for c in cols}, rid=rid))
        return rid.getvalue()[0]


def update_row(T, pk, vals):
    sets = ", ".join(f"{c} = :v_{c}" for c in vals)
    return db.execute(f"UPDATE {T['table']} SET {sets} WHERE {T['pk']} = :pk",
                      dict({"v_" + c: v for c, v in vals.items()}, pk=pk))


def load_row(T, pk):
    row = db.one(f"{inner_select(T)} WHERE t.{T['pk']} = :pk", {"pk": pk})
    if not row:
        abort(404)
    return row


def conv_pk(T, pk):
    if T["pk_int"]:
        try:
            return int(pk)
        except ValueError:
            abort(404)
    return pk


def related_counts(T, pk):
    out = []
    for rt, col in T["related"]:
        n = db.scalar(f"SELECT COUNT(*) FROM {rt} WHERE {col} = :pk", {"pk": pk})
        out.append(dict(table=rt, col=col, title=TABLES[rt]["title"], n=n))
    return out


def next_order_no():
    n = db.scalar("SELECT MAX(TO_NUMBER(order_no DEFAULT NULL ON CONVERSION ERROR)) FROM orders")
    return f"{int(n or 0) + 1:04d}"


@app.route("/<table>/new", methods=["GET", "POST"])
@app.route("/<table>/<pk>/edit", methods=["GET", "POST"])
def table_form(table, pk=None):
    T = get_table(table)
    is_new = pk is None
    if not is_new:
        pk = conv_pk(T, pk)
        if table == "orders":
            return redirect(url_for("order_detail", oid=pk))
    row = None if is_new else load_row(T, pk)
    errors = {}
    if request.method == "POST":
        vals, errors = parse_form(T, request.form)
        if not errors:
            before_save(table, vals, is_new)
            try:
                if is_new:
                    pk = insert_row(T, vals)
                else:
                    update_row(T, pk, vals)
                db.commit()
                flash(f"{T['one'].capitalize()} salvat(ă).", "ok")
                if table == "orders" and is_new:
                    return redirect(url_for("order_detail", oid=pk))
                return redirect(request.form.get("_back") or url_for("table_list", table=table))
            except oracledb.DatabaseError as e:
                errors["_"] = db_error(e)
        inputs = request.form.to_dict()
    elif is_new:
        inputs = default_inputs(T)
        if table == "orders":
            inputs["order_no"] = next_order_no()
    else:
        inputs = {f["name"]: to_input(f, row.get(f["name"])) for f in T["fields"]}
    back = request.form.get("_back") or request.referrer
    if not back or "/edit" in back or "/new" in back or not back.startswith(request.host_url):
        back = url_for("table_list", table=table)
    return render_template(
        "form.html", T=T, table=table, pk=pk, row=row, is_new=is_new, inputs=inputs,
        errors=errors, opts=fk_options(T), sug=suggestions(T), back=back,
        related=[] if is_new else related_counts(T, pk))


@app.route("/<table>/<pk>/delete", methods=["POST"])
def table_delete(table, pk):
    T = get_table(table)
    pk = conv_pk(T, pk)
    try:
        db.execute(f"DELETE FROM {T['table']} WHERE {T['pk']} = :pk", {"pk": pk})
        db.commit()
        flash(f"{T['one'].capitalize()} șters(ă).", "ok")
        return redirect(url_for("table_list", table=table))
    except oracledb.DatabaseError as e:
        flash(db_error(e), "err")
        if table == "orders":
            return redirect(url_for("order_detail", oid=pk))
        return redirect(url_for("table_form", table=table, pk=pk))


@app.route("/companies/<pk>/to-client", methods=["POST"])
def company_to_client(pk):
    c = db.one("SELECT * FROM companies WHERE company_key = :k", {"k": pk})
    if not c:
        abort(404)
    cid = db.scalar("SELECT id FROM clients WHERE idno = :i", {"i": c["idno"]})
    if cid:
        flash("Compania este deja în lista de clienți.", "ok")
    else:
        cid = insert_row(TABLES["clients"], dict(
            denumire=c["denumire"], idno=c["idno"], forma_juridica=c["forma_juridica"],
            inregistrare=c["inregistrare"], lichidata=c["lichidata"], adresa=c["adresa"],
            administrator=(c["administratori"] or "")[:400] or None,
            details=c["details_text"], source="date.gov.md", client_type="Клиент"))
        db.commit()
        flash("Client creat din registrul de companii.", "ok")
    return redirect(url_for("table_form", table="clients", pk=cid))


@app.route("/tasks/<int:tid>/toggle", methods=["POST"])
def task_toggle(tid):
    db.execute("""UPDATE tasks SET done = 1 - NVL(done,0),
                  stage = CASE WHEN NVL(done,0) = 0 THEN 'Готово'
                               WHEN stage = 'Готово' THEN 'В работе' ELSE stage END
                  WHERE id = :i""", {"i": tid})
    db.commit()
    back = request.form.get("_back", "")
    ok = back.startswith(request.script_root + "/") and not back.startswith("//")
    return redirect(back if ok else url_for("dashboard"))


# ---------------------------------------------------------------- comenzi (master-detail)

def recalc_order(oid):
    db.execute("""UPDATE orders SET total = (SELECT NVL(SUM(line_sum),0) FROM order_lines
                  WHERE order_id = :i) WHERE id = :i""", {"i": oid})


def line_values(form):
    errors = []
    item_id, e1 = parse_value(dict(type="fk", req=True), form.get("item_id"))
    qty, e2 = parse_value(dict(type="num", req=True), form.get("qty"))
    price, e3 = parse_value(dict(type="money"), form.get("price"))
    errors = [e for e in (e1 and "Alegeți produsul.", e2 and "Cantitate invalidă.", e3) if e]
    if not errors and price is None:
        price = db.scalar("SELECT price FROM items WHERE id = :i", {"i": item_id}) or Decimal(0)
    if not errors and qty <= 0:
        errors.append("Cantitatea trebuie să fie pozitivă.")
    vals = None
    if not errors:
        line_sum = (Decimal(qty) * Decimal(price)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        vals = dict(item_id=item_id, qty=qty, price=price, line_sum=line_sum)
    return vals, errors


@app.route("/orders/<int:oid>", methods=["GET", "POST"])
def order_detail(oid):
    T = TABLES["orders"]
    row = load_row(T, oid)
    errors = {}
    if request.method == "POST":
        vals, errors = parse_form(T, request.form)
        if not errors:
            try:
                update_row(T, oid, vals)
                db.commit()
                flash("Comanda a fost salvată.", "ok")
                return redirect(url_for("order_detail", oid=oid))
            except oracledb.DatabaseError as e:
                errors["_"] = db_error(e)
        inputs = request.form.to_dict()
    else:
        inputs = {f["name"]: to_input(f, row.get(f["name"])) for f in T["fields"]}
    lines = db.query("""
        SELECT l.id, l.item_id, l.qty, l.price, l.line_sum, i.name item_name, i.code, i.unit_
          FROM order_lines l JOIN items i ON i.id = l.item_id
         WHERE l.order_id = :o ORDER BY l.id""", {"o": oid})
    items = db.query("SELECT id, code, name, price, unit_ FROM items ORDER BY name")
    return render_template("order.html", T=T, table="orders", pk=oid, row=row, inputs=inputs,
                           errors=errors, opts=fk_options(T), sug={}, lines=lines,
                           items=items, back=url_for("table_list", table="orders"))


@app.route("/orders/<int:oid>/lines/add", methods=["POST"])
@app.route("/orders/<int:oid>/lines/<int:lid>/edit", methods=["POST"])
def order_line_save(oid, lid=None):
    load_row(TABLES["orders"], oid)
    vals, errors = line_values(request.form)
    if errors:
        for e in errors:
            flash(e, "err")
        return redirect(url_for("order_detail", oid=oid) + "#pozitii")
    try:
        if lid is None:
            insert_row(dict(table="order_lines", pk="id", pk_int=True), dict(vals, order_id=oid))
        else:
            update_row(dict(table="order_lines", pk="id"), lid, vals)
        recalc_order(oid)
        db.commit()
        flash("Poziția a fost salvată.", "ok")
    except oracledb.DatabaseError as e:
        flash(db_error(e), "err")
    return redirect(url_for("order_detail", oid=oid) + "#pozitii")


@app.route("/orders/<int:oid>/lines/<int:lid>/delete", methods=["POST"])
def order_line_delete(oid, lid):
    db.execute("DELETE FROM order_lines WHERE id = :l AND order_id = :o", {"l": lid, "o": oid})
    recalc_order(oid)
    db.commit()
    flash("Poziția a fost ștearsă.", "ok")
    return redirect(url_for("order_detail", oid=oid) + "#pozitii")


# ---------------------------------------------------------------- Kanban

@app.route("/<table>/kanban")
def table_kanban(table):
    T = get_table(table)
    K = KANBAN.get(table)
    if not K:
        abort(404)
    remember_view(table, "kanban")
    fld = K["field"]
    choices_key = T["by_name"][fld]["choices"]
    choices = CHOICES[choices_key]
    q = request.args.get("q", "").strip()
    args = {k: v for k, v in request.args.items() if k != fld}  # coloanele sunt chiar etapele
    where, binds, chips = build_filters(T, args, q)
    base = filtered_base(T, where)

    sum_expr = f"NVL(SUM({K['sum']}),0)" if K.get("sum") else "0"
    stats = {r["v"]: r for r in db.query(
        f"SELECT {fld} v, COUNT(*) n, {sum_expr} s FROM ({base}) GROUP BY {fld}", binds)}
    order, direction = K.get("order", T["sort"])
    rows = db.query(f"""
        SELECT * FROM (
          SELECT b.*, ROW_NUMBER() OVER (PARTITION BY {fld}
                 ORDER BY {order} {direction} NULLS LAST, {T['pk']}) kb_rn
            FROM ({base}) b)
         WHERE kb_rn <= :lim ORDER BY kb_rn""", dict(binds, lim=KANBAN_PER_COLUMN))
    cards = defaultdict(list)
    for r in rows:
        r["href"] = row_href(table, T, r)
        cards[r[fld]].append(r)

    # etapele cunoscute, in ordinea procesului; valorile necunoscute/goale la sfarsit
    columns = []
    for v in choices + [v for v in stats if v not in choices]:
        st = stats.get(v, {})
        columns.append(dict(value=v or "", label=ro(v) if v else "Fără etapă",
                            color=stage_color(choices_key, v) or "#a8adb4",
                            n=st.get("n", 0), s=st.get("s", 0), cards=cards.get(v, []),
                            drop=v in choices))
    return render_template("kanban.html", T=T, K=K, table=table, columns=columns,
                           meta=[T["by_name"][m] for m in K["meta"]], q=q, chips=chips,
                           total=sum(c["n"] for c in columns),
                           filtered=bool(q or chips or any(args.get(n) for n in T["filters"])),
                           prefill={f["name"]: request.args[f["name"]] for f, _ in chips})


@app.route("/<table>/<pk>/move", methods=["POST"])
def kanban_move(table, pk):
    """Mutarea unui card Kanban: salveaza noua etapa/status (apel fetch, raspuns JSON)."""
    T = get_table(table)
    K = KANBAN.get(table)
    if not K:
        abort(404)
    pk = conv_pk(T, pk)
    fld = K["field"]
    v = request.form.get("value", "")
    if v not in CHOICES[T["by_name"][fld]["choices"]]:
        return jsonify(ok=False, error="Etapă necunoscută."), 400
    sets = f"{fld} = :v"
    if table == "tasks":  # ca butonul „Marchează ca făcută”: etapa Gata <=> făcută
        sets += ", done = CASE WHEN :v = 'Готово' THEN 1 ELSE 0 END"
    try:
        n = db.execute(f"UPDATE {T['table']} SET {sets} WHERE {T['pk']} = :pk",
                       {"v": v, "pk": pk})
        db.commit()
    except oracledb.DatabaseError as e:
        return jsonify(ok=False, error=db_error(e)), 500
    if not n:
        return jsonify(ok=False, error="Înregistrarea nu mai există."), 404
    return jsonify(ok=True, value=v, label=ro(v))


# ---------------------------------------------------------------- cautare globala

SEARCH_TABLES = ["clients", "contacts", "leads", "deals", "orders", "tasks", "projects",
                 "items", "companies"]


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    groups = []
    if q:
        for table in SEARCH_TABLES:
            T = TABLES[table]
            where, binds, _ = build_filters(T, {}, q)
            base = filtered_base(T, where)
            n = db.scalar(f"SELECT COUNT(*) FROM ({base})", binds)
            if not n:
                continue
            sort, direction = T["sort"]
            rows = db.query(f"{base} ORDER BY {sort} {direction} NULLS LAST, {T['pk']}"
                            f" FETCH FIRST 5 ROWS ONLY", binds)
            for r in rows:
                r["href"] = row_href(table, T, r)
            groups.append(dict(table=table, T=T, n=n, rows=rows,
                               cols=[f for f in T["fields"] if f.get("list")][:4]))
    return render_template("search.html", q=q, groups=groups,
                           total=sum(g["n"] for g in groups))


# ---------------------------------------------------------------- calendar sarcini

@app.route("/calendar")
def calendar():
    today = dt.date.today()
    try:
        y, m = (int(x) for x in request.args.get("m", "").split("-"))
        first = dt.date(y, m, 1)
    except ValueError:
        first = today.replace(day=1)
    nxt = (first + dt.timedelta(days=32)).replace(day=1)
    prev = (first - dt.timedelta(days=1)).replace(day=1)
    only_open = request.args.get("open") == "1"
    sql = """SELECT t.id, t.subject, t.due_at, NVL(t.done,0) done, t.priority, t.assignee,
                    (SELECT c.denumire FROM clients c WHERE c.id = t.client_id) client
               FROM tasks t WHERE t.due_at >= :a AND t.due_at < :b"""
    if only_open:
        sql += " AND NVL(t.done,0) = 0"
    rows = db.query(sql + " ORDER BY t.due_at, t.id",
                    {"a": dt.datetime.combine(first, dt.time()),
                     "b": dt.datetime.combine(nxt, dt.time())})
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["due_at"].date()].append(r)
    weeks = _calendar.Calendar(0).monthdatescalendar(first.year, first.month)
    return render_template("calendar.html", first=first, weeks=weeks, by_day=by_day,
                           month_name=f"{MONTHS[first.month]} {first.year}",
                           prev=prev.strftime("%Y-%m"), nxt=nxt.strftime("%Y-%m"),
                           weekdays=WEEKDAYS, only_open=only_open, n=len(rows))



@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, msg="Pagina nu a fost găsită."), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, msg=e.description), 400


@app.errorhandler(500)
def server_error(_e):
    return render_template("error.html", code=500, msg="Eroare internă a serverului."), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5002)), debug=False)
