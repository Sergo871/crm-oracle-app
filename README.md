# crm-oracle-app — Demo CRM pe Oracle ADB

Aplicație web Flask + python-oracledb peste tabelele Demo CRM
([Contragenti](https://github.com/PavelTuhari/Contragenti)) încărcate în schema
**CRM_DEMO** a unei baze Oracle Autonomous Database. Este o alternativă la APEX.

Online: <https://flask-hello-oracle.duckdns.org/crm/>

## Funcționalități

- **Aspect în stilul Bitrix24 CRM**: meniu lateral închis cu iconițe și secțiuni (se poate
  restrânge; pe telefon se deschide din ☰), bara de sus cu căutare globală și utilizatorul,
  carduri albe pe fundal gri-albastru, butoane și culori de etapă ca în Bitrix24.
- **Kanban cu drag-and-drop** (comutator Kanban/Listă): oferte după etapă (cu suma pe coloană),
  sarcini după etapă, comenzi după status (cu total), lead-uri după status. Mutarea unui card
  salvează noua etapă în bază (POST cu token CSRF); pe telefon: apăsare lungă și tragere sau
  meniul ⋯ de pe card. Pentru sarcini, etapa „Gata” marchează sarcina ca făcută.
- **Căutare globală** în clienți, contacte, lead-uri, oferte, comenzi, sarcini, proiecte etc.
- **Panou**: oferte pe etape (număr și sumă), comenzi pe status, sarcini deschise
  (cu marcare rapidă ca făcute), top clienți după valoarea comenzilor.
- **Liste** pentru clienți, contacte, lead-uri, oferte, proiecte, sarcini, produse și companii,
  fiecare cu căutare, sortare pe coloane, filtre, paginare și formular de
  adăugare/editare/ștergere. Legăturile (client, proiect, ofertă, produs) se aleg din
  liste derulante care afișează **numele**, nu id-ul.
- **Comenzi master-detail**: antetul comenzii și pozițiile ei. Suma poziției = cantitate × preț,
  iar totalul comenzii se recalculează automat. Prețul se preia din catalog.
- **Calendar** lunar pentru sarcini, după `due_at` (pe telefon se afișează ca agendă).
- **Companii** (registrul date.gov.md): butonul „Adaugă ca client”.
- Interfață în limba română, adaptată pentru telefon, cu temă luminoasă/întunecată.
  Valorile categoriale din bază (în rusă, ca în Demo CRM) se afișează traduse.
- **Autentificare**: utilizatorii sunt în tabelul `users`, iar parola se stochează doar ca hash
  (Werkzeug scrypt). Toate formularele au protecție CSRF.

## Structură

```
app.py        rute Flask (panou, liste/formulare generice, Kanban, căutare, comenzi, calendar, login)
schema.py     descrierea tabelelor: câmpuri, etichete, legături, traduceri
db.py         pool de conexiuni python-oracledb (thin mode, wallet)
manage.py     administrare utilizatori (set-password, list-users)
templates/    șabloane Jinja
static/       CSS și kanban.js (drag-and-drop)
deploy/       unitate systemd + fragment nginx pentru /crm/
```

## Instalare

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env      # completați DB_PASSWORD, WALLET_PASSWORD, SECRET_KEY
venv/bin/python manage.py set-password director "Director"
venv/bin/gunicorn -w 2 -b 127.0.0.1:5002 app:app
```

Cont demonstrativ: **DEMO / DEMO123** — formularul de logare vine precompletat, se apasă doar „Intră”. Utilizatorul DEMO se creează automat în tabelul `users` (parola doar ca hash); se dezactivează cu `DEMO_LOGIN=` gol în `.env`.

Conexiunea se face ca **CRM_DEMO** (nu ADMIN). Fișierul `.env` și wallet-ul nu se pun în git.

## Publicare pe VM (nginx + systemd)

1. `sudo cp deploy/crm-oracle-app.service /etc/systemd/system/ && sudo systemctl enable --now crm-oracle-app`
2. Adăugați conținutul din `deploy/nginx-crm-location.conf` în blocul `server` HTTPS existent,
   apoi rulați `sudo nginx -t && sudo systemctl reload nginx`.
3. Cu SELinux activ, executabilele din venv au nevoie de eticheta `bin_t`:
   `sudo semanage fcontext -a -t bin_t "/home/opc/crm-oracle-app/venv/bin(/.*)?" && sudo restorecon -R venv/bin`

Aplicația primește prefixul `/crm` prin antetul `X-Forwarded-Prefix` (Werkzeug ProxyFix).
