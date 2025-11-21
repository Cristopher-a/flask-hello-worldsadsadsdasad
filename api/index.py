from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)  # ← Habilita CORS en todo

SUPABASE_URL = "https://rhttqmtzcmwilzshnxwq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJodHRxbXR6Y213aWx6c2hueHdxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjM1OTUwOTAsImV4cCI6MjA3OTE3MTA5MH0.8dYvM8CBEdqiF9ZZhaYRKhtOin_wYGf4JYrmTTIsX74"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route("/ranking", methods=["POST"])
def ranking():
    body = request.get_json()
    eventCode = body.get("eventCode")

    if not eventCode:
        return jsonify({"error": "eventCode requerido"}), 400

    try:
        # -------------------------
        # 1️⃣ Cargar datos de Supabase
        # -------------------------
        pits = supabase.table("pit_scouting").select("*").execute().data or []
        matches = supabase.table("match_scouting").select("*").execute().data or []

        if not pits or not matches:
            return jsonify([])

        pits_index = {(p["team_number"], p["region"]): p for p in pits}

        # -------------------------
        # 2️⃣ Unir matches + pits
        # -------------------------
        unidos = []
        for m in matches:
            key = (m["team_number"], m["regional"])
            pit = pits_index.get(key, {})
            unidos.append({**pit, **m})

        # -------------------------
        # 3️⃣ Calcular score por match
        # -------------------------
        score_cols = [
            'check_inicio', 'count_motiv',
            'count_in_cage_auto', 'count_out_cage_auto',
            'count_in_cage_teleop', 'count_out_cage_teleop',
            'count_rp', 'check_scoring',
            'count_in_cage_endgame', 'count_out_cage_endgame',
            'check_full_park', 'check_partial_park', 'check_high',
            'cycle_number', 'artifacts_number', 'check1'
        ]

        for row in unidos:
            total = 0
            for col in score_cols:
                try:
                    total += float(row.get(col, 0) or 0)
                except:
                    total += 0
            row["score"] = total

        # -------------------------
        # 4️⃣ Agrupar por equipo
        # -------------------------
        teams = {}
        for row in unidos:
            t = row["team_number"]
            if t not in teams:
                teams[t] = {
                    "team_number": t,
                    "score_list": [],
                    "auto_in": 0,
                    "teleop_in": 0,
                }

            teams[t]["score_list"].append(row["score"])
            teams[t]["auto_in"] += float(row.get("count_in_cage_auto", 0) or 0)
            teams[t]["teleop_in"] += float(row.get("count_in_cage_teleop", 0) or 0)

        # Score promedio por equipo
        for t in teams.values():
            scores = t["score_list"]
            t["score"] = round(sum(scores) / len(scores), 2) if scores else 0

        # -------------------------
        # 5️⃣ Ranking FTC (API segura)
        # -------------------------
        def ftc_rank(team, eventCode):
            try:
                url = f"http://ftc-api.firstinspires.org/v2.0/2025/rankings/{eventCode}"
                r = requests.get(
                    url,
                    auth=HTTPBasicAuth(
                        "crisesv4",
                        "E936A6EC-14B0-4904-8DF4-E4916CA4E9BB"
                    )
                )

                print("URL:", url)
                print("STATUS:", r.status_code)
                print("BODY:", r.text[:200])  # solo primeros 200 caracteres

                if r.status_code != 200:
                    return None

                data = r.json()
                ranks = data.get("rankings")
                if not isinstance(ranks, list):
                    print("FORMATO INVALIDO DE RANKINGS", ranks)
                    return None

                for item in ranks:
                    if item.get("teamNumber") == team:
                        return item.get("rank")

            except Exception as e:
                print("FTC ERROR:", e)
                return None

            return None

        for t in teams.values():
            t["ftc_rank"] = ftc_rank(t["team_number"], eventCode)

        # -------------------------
        # 6️⃣ Calcular alliance_score
        # -------------------------
        for t in teams.values():
            auto = t["auto_in"]
            tele = t["teleop_in"]
            score = t["score"]

            # Eficiencia segura
            eff = (auto + tele) / (score + 1)

            # FTC rank seguro
            rank = t["ftc_rank"]
            if isinstance(rank, (int, float)) and rank > 0:
                frs = 1 / rank
            else:
                frs = 0

            t["alliance_score"] = round(score * 0.6 + eff * 0.3 + frs * 0.1, 4)

        # -------------------------
        # 7️⃣ Ordenar y regresar
        # -------------------------
        result = sorted(
            teams.values(),
            key=lambda x: x["alliance_score"],
            reverse=True
        )

        return jsonify(result)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print("ERROR:\n", tb)
        return jsonify({"error": str(e), "traceback": tb}), 500
