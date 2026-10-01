"""Descrierea tabelelor din schema CRM_DEMO: campuri, etichete romanesti, legaturi.

Valorile categoriale sunt stocate in baza asa cum au venit din Demo CRM (in rusa);
interfata le afiseaza in romana prin dictionarul RO.
"""

RO = {
    # tip client
    "Клиент": "Client", "Партнёр": "Partener", "Поставщик": "Furnizor",
    # lead-uri
    "Новый": "Nou", "В работе": "În lucru", "Конвертирован": "Convertit", "Отказ": "Refuz",
    "Сайт": "Site", "Звонок": "Apel", "Реклама": "Publicitate", "Выставка": "Expoziție",
    "Рекомендация": "Recomandare", "Другое": "Altele",
    # oferte
    "Новая": "Nouă", "Предложение": "Ofertă trimisă", "Переговоры": "Negocieri",
    "Выиграна": "Câștigată", "Проиграна": "Pierdută",
    # produse
    "Товар": "Marfă", "Изделие": "Produs", "Услуга": "Serviciu",
    "шт": "buc", "час": "oră", "компл": "set", "м": "m", "кг": "kg", "л": "l", "услуга": "serviciu",
    # proiecte
    "Сувениры": "Suveniruri", "Гравировка": "Gravură", "Монтаж": "Montaj",
    "Тендер": "Licitație", "Договор": "Contract", "Аванс": "Avans", "Дизайн": "Design",
    "Производство": "Producție", "Сдача": "Predare", "Оплата": "Plată", "Закрыт": "Închis",
    "Проигран": "Pierdut",
    # comenzi
    "Продажа": "Vânzare", "Черновик": "Ciornă", "Подтверждён": "Confirmată",
    "Выполнен": "Executată", "Оплачен": "Achitată", "Отменён": "Anulată",
    # sarcini
    "Задача": "Sarcină", "Встреча": "Întâlnire", "Ожидание": "În așteptare", "Готово": "Gata",
    "Низкий": "Scăzută", "Обычный": "Normală", "Высокий": "Înaltă", "Срочно": "Urgentă",
}

CHOICES = {
    "client_type": ["Клиент", "Партнёр", "Поставщик"],
    "lead_status": ["Новый", "В работе", "Конвертирован", "Отказ"],
    "lead_source": ["Сайт", "Звонок", "Реклама", "Выставка", "Рекомендация", "Другое"],
    "deal_stage": ["Новая", "Предложение", "Переговоры", "Выиграна", "Проиграна"],
    "item_kind": ["Товар", "Изделие", "Услуга"],
    "unit": ["шт", "час", "компл", "м", "кг", "л", "услуга"],
    "project_kind": ["Реклама", "Сувениры", "Гравировка", "Монтаж"],
    "project_status": ["Тендер", "Договор", "Аванс", "Дизайн", "Производство", "Сдача",
                       "Оплата", "Закрыт", "Проигран"],
    "order_kind": ["Продажа", "Производство", "Услуга"],
    "order_status": ["Черновик", "Подтверждён", "В работе", "Выполнен", "Оплачен", "Отменён"],
    "task_kind": ["Задача", "Звонок", "Встреча"],
    "task_stage": ["Новая", "В работе", "Ожидание", "Готово"],
    "priority": ["Низкий", "Обычный", "Высокий", "Срочно"],
}

# tabel referit -> coloana afisata in listele derulante
LOOKUPS = {
    "clients": "denumire",
    "projects": "name",
    "items": "name",
    "deals": "title",
    "tasks": "subject",
}


def F(name, label, type="text", **kw):
    """type: text, tel, email, textarea, int, num, money, date, datetime, choice, fk, bool.
    kw: req, list, search, choices, ref, suggest, ro (doar afisare), wide, default."""
    d = dict(name=name, label=label, type=type)
    d.update(kw)
    return d


TABLES = {
    "clients": dict(
        title="Clienți", one="client", sort=("denumire", "asc"), filters=["client_type"],
        related=[("contacts", "client_id"), ("leads", "client_id"), ("deals", "client_id"),
                 ("projects", "client_id"), ("orders", "client_id"), ("tasks", "client_id")],
        fields=[
            F("denumire", "Denumire", req=True, list=True, search=True, wide=True),
            F("idno", "IDNO", list=True, search=True),
            F("client_type", "Tip", "choice", choices="client_type", list=True, search=True,
              default="Клиент"),
            F("phone", "Telefon", "tel", list=True, search=True),
            F("email", "E-mail", "email", list=True, search=True),
            F("contact_person", "Persoană de contact", search=True),
            F("administrator", "Administrator", search=True),
            F("forma_juridica", "Formă juridică", suggest=True),
            F("inregistrare", "Data înregistrării", "date"),
            F("lichidata", "Lichidată", suggest=True),
            F("source", "Sursă", suggest=True),
            F("adresa", "Adresă", search=True, wide=True),
            F("notes", "Note", "textarea", wide=True),
            F("details", "Detalii (registru)", "textarea", wide=True),
            F("added_at", "Adăugat", "datetime", ro=True, list=True),
        ]),
    "contacts": dict(
        title="Contacte", one="contact", sort=("name", "asc"), filters=[],
        fields=[
            F("name", "Nume", req=True, list=True, search=True),
            F("client_id", "Client", "fk", ref="clients", list=True, search=True),
            F("position", "Funcție", list=True, search=True, suggest=True),
            F("phone", "Telefon", "tel", list=True, search=True),
            F("email", "E-mail", "email", list=True, search=True),
            F("notes", "Note", "textarea", wide=True),
        ]),
    "leads": dict(
        title="Lead-uri", one="lead", sort=("created_at", "desc"), filters=["status", "source"],
        fields=[
            F("name", "Nume", req=True, list=True, search=True),
            F("company", "Companie", list=True, search=True),
            F("status", "Status", "choice", choices="lead_status", list=True, search=True,
              default="Новый"),
            F("source", "Sursă", "choice", choices="lead_source", list=True, search=True),
            F("phone", "Telefon", "tel", search=True),
            F("email", "E-mail", "email", search=True),
            F("client_id", "Client (după conversie)", "fk", ref="clients"),
            F("notes", "Note", "textarea", wide=True),
            F("created_at", "Creat", "datetime", ro=True, list=True),
        ]),
    "deals": dict(
        title="Oferte", one="ofertă", sort=("close_date", "desc"), filters=["stage"],
        related=[("tasks", "deal_id")],
        fields=[
            F("title", "Titlu", req=True, list=True, search=True, wide=True),
            F("client_id", "Client", "fk", ref="clients", list=True, search=True),
            F("stage", "Etapă", "choice", choices="deal_stage", list=True, search=True,
              default="Новая"),
            F("amount", "Sumă", "money", list=True, default=0),
            F("close_date", "Data închiderii", "date", list=True),
            F("notes", "Note", "textarea", wide=True),
            F("created_at", "Creat", "datetime", ro=True),
        ]),
    "projects": dict(
        title="Proiecte", one="proiect", sort=("due_date", "desc"), filters=["kind", "status"],
        related=[("orders", "project_id"), ("tasks", "project_id")],
        fields=[
            F("name", "Denumire", req=True, list=True, search=True, wide=True),
            F("client_id", "Client", "fk", ref="clients", list=True, search=True),
            F("kind", "Tip", "choice", choices="project_kind", list=True, search=True),
            F("status", "Status", "choice", choices="project_status", list=True, search=True),
            F("manager", "Manager", list=True, search=True, suggest=True),
            F("budget", "Buget", "money", list=True, default=0),
            F("prepay_pct", "Avans, %", "num", default=0),
            F("prepaid", "Avans achitat", "money", default=0),
            F("paid", "Achitat", "money", default=0),
            F("tender_no", "Nr. licitație", search=True),
            F("tender_deadline", "Termen licitație", "date"),
            F("start_date", "Început", "date"),
            F("due_date", "Termen", "date", list=True),
            F("notes", "Note", "textarea", wide=True),
            F("created_at", "Creat", "datetime", ro=True),
        ]),
    "tasks": dict(
        title="Sarcini", one="sarcină", sort=("due_at", "desc"),
        filters=["done", "stage", "priority", "kind"],
        fields=[
            F("subject", "Subiect", req=True, list=True, search=True, wide=True),
            F("kind", "Tip", "choice", choices="task_kind", list=True, search=True,
              default="Задача"),
            F("due_at", "Termen", "date", list=True),
            F("client_id", "Client", "fk", ref="clients", list=True, search=True),
            F("project_id", "Proiect", "fk", ref="projects", search=True),
            F("deal_id", "Ofertă", "fk", ref="deals"),
            F("stage", "Etapă", "choice", choices="task_stage", list=True, search=True,
              default="Новая"),
            F("priority", "Prioritate", "choice", choices="priority", list=True, search=True,
              default="Обычный"),
            F("assignee", "Responsabil", list=True, search=True, suggest=True),
            F("done", "Făcută", "bool", list=True),
            F("plan_start", "Început planificat", "date"),
            F("hours_plan", "Ore planificate", "num"),
            F("hours_fact", "Ore efective", "num"),
            F("depends_on", "Depinde de", "fk", ref="tasks"),
            F("seq", "Ordine", "int"),
            F("notes", "Note", "textarea", wide=True),
            F("created_at", "Creat", "datetime", ro=True),
        ]),
    "items": dict(
        title="Produse", one="produs", sort=("name", "asc"), filters=["kind"],
        fields=[
            F("code", "Cod", list=True, search=True),
            F("name", "Denumire", req=True, list=True, search=True, wide=True),
            F("kind", "Tip", "choice", choices="item_kind", list=True, search=True,
              default="Товар"),
            F("unit_", "UM", "choice", choices="unit", list=True, default="шт"),
            F("price", "Preț", "money", list=True, default=0),
            F("vat", "TVA, %", "num", list=True, default=20),
            F("stock", "Stoc", "num", list=True, default=0),
            F("notes", "Note", "textarea", wide=True),
        ]),
    "orders": dict(
        title="Comenzi", one="comandă", sort=("order_date", "desc"), filters=["status", "kind"],
        fields=[
            F("order_no", "Nr.", req=True, list=True, search=True),
            F("order_date", "Data", "date", list=True, default="today"),
            F("client_id", "Client", "fk", ref="clients", list=True, search=True),
            F("project_id", "Proiect", "fk", ref="projects", search=True),
            F("kind", "Tip", "choice", choices="order_kind", list=True, search=True,
              default="Продажа"),
            F("status", "Status", "choice", choices="order_status", list=True, search=True,
              default="Черновик"),
            F("total", "Total", "money", ro=True, list=True),
            F("advance", "Avans", "money"),
            F("paid", "Achitat", "money", list=True),
            F("due_date", "Termen plată", "date"),
            F("ship_date", "Data livrării", "date"),
            F("posted", "Înregistrată în ERP", "bool"),
            F("notes", "Note", "textarea", wide=True),
        ]),
    "companies": dict(
        title="Companii", one="companie", sort=("denumire", "asc"), filters=[],
        pk="company_key", pk_int=False,
        fields=[
            F("denumire", "Denumire", req=True, list=True, search=True, wide=True),
            F("idno", "IDNO", req=True, list=True, search=True),
            F("forma_juridica", "Formă juridică", list=True, search=True, suggest=True),
            F("inregistrare", "Înregistrare", "date", list=True),
            F("lichidata", "Lichidată", list=True, suggest=True),
            F("administratori", "Administratori", search=True, wide=True),
            F("adresa", "Adresă", search=True, wide=True),
            F("details_text", "Detalii", "textarea", wide=True),
            F("founders_json", "Fondatori (JSON)", "textarea", wide=True),
            F("debts_json", "Datorii (JSON)", "textarea", wide=True),
            F("updated_at", "Actualizat", "datetime", ro=True),
        ]),
}

for _key, _t in TABLES.items():
    _t.setdefault("table", _key)
    _t.setdefault("pk", "id")
    _t.setdefault("pk_int", True)
    _t.setdefault("related", [])
    _t["by_name"] = {f["name"]: f for f in _t["fields"]}

NAV = [
    ("dashboard", "Panou"), ("clients", "Clienți"), ("contacts", "Contacte"),
    ("leads", "Lead-uri"), ("deals", "Oferte"), ("orders", "Comenzi"),
    ("projects", "Proiecte"), ("tasks", "Sarcini"), ("calendar", "Calendar"),
    ("items", "Produse"), ("companies", "Companii"),
]
