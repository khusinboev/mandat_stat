"""webapp/main.py — O'tish ballari Telegram mini webapp backend.

Faqat ko'rsatish (read-only) API: bazadagi 2025-yil mandat ma'lumotlarini
mobil SPA'ga JSON qilib beradi. Bot bilan hech qanday bog'lanish yo'q.

Ishga tushirish:
    .venv/bin/uvicorn webapp.main:app --host 0.0.0.0 --port 8080
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from webapp.db import SQL_NORM, close_pool, fetch, fetchrow, get_pool, norm_query

YEAR = 2025
STATIC_DIR = Path(__file__).parent / "static"

# ty_id/lan_id → nom xaritalari startupda DB'dan yuklanadi
TY_NAMES: dict[str, str] = {}
LAN_NAMES: dict[str, str] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    for r in await fetch("SELECT DISTINCT ty_id, ty_text FROM gettypes"):
        TY_NAMES[r["ty_id"]] = r["ty_text"]
    for r in await fetch("SELECT DISTINCT lan_id, lan_text FROM getlangs"):
        LAN_NAMES[r["lan_id"]] = r["lan_text"]
    yield
    await close_pool()


app = FastAPI(title="O'tish ballari 2025", lifespan=lifespan)


def _ty(ty_id: str) -> str:
    return TY_NAMES.get(ty_id, ty_id)


def _lan(lan_id: str) -> str:
    return LAN_NAMES.get(lan_id, lan_id)


@app.get("/api/stats")
async def stats():
    row = await fetchrow(
        """
        SELECT
          (SELECT COUNT(*) FROM regions)                          AS regions,
          (SELECT COUNT(*) FROM universities)                     AS universities,
          (SELECT COUNT(DISTINCT nomi) FROM mandat WHERE year=$1) AS directions,
          (SELECT COUNT(*) FROM mandat WHERE year=$1)             AS records,
          (SELECT ROUND(MIN(con_b) FILTER (WHERE con_b>0)::numeric,1)
             FROM mandat WHERE year=$1)                           AS min_ball,
          (SELECT ROUND(MAX(con_b)::numeric,1)
             FROM mandat WHERE year=$1)                           AS max_ball
        """,
        YEAR,
    )
    top = await fetch(
        """
        SELECT u.un_text, m.nomi, m.ty_id, m.lan_id,
               ROUND(m.con_b::numeric,1) AS ball
        FROM mandat m JOIN universities u ON m.un_id = u.un_id
        WHERE m.year = $1 AND m.con_b > 0
        ORDER BY m.con_b DESC LIMIT 5
        """,
        YEAR,
    )
    return {
        **dict(row),
        "min_ball": float(row["min_ball"]),
        "max_ball": float(row["max_ball"]),
        "year": YEAR,
        "top": [
            {
                "un_text": t["un_text"],
                "nomi": t["nomi"],
                "ty": _ty(t["ty_id"]),
                "lan": _lan(t["lan_id"]),
                "ball": float(t["ball"]),
            }
            for t in top
        ],
    }


@app.get("/api/regions")
async def regions():
    rows = await fetch(
        """
        SELECT r.region_id AS id, r.region_name AS name,
               COUNT(DISTINCT u.un_id) AS unis,
               COUNT(DISTINCT m.nomi)  AS dirs
        FROM regions r
        LEFT JOIN universities u ON u.region_id = r.region_id
        LEFT JOIN mandat m ON m.region_id = r.region_id AND m.year = $1
        GROUP BY r.region_id, r.region_name
        ORDER BY r.region_id
        """,
        YEAR,
    )
    return [dict(r) for r in rows]


@app.get("/api/region/{region_id}/universities")
async def region_universities(region_id: int):
    rows = await fetch(
        """
        SELECT u.un_id, u.un_text AS name,
               COUNT(m.id) AS dirs,
               ROUND(MIN(m.con_b) FILTER (WHERE m.con_b>0)::numeric,1) AS min_ball,
               ROUND(MAX(m.con_b)::numeric,1) AS max_ball
        FROM universities u
        LEFT JOIN mandat m ON m.un_id = u.un_id AND m.year = $2
        WHERE u.region_id = $1
        GROUP BY u.un_id, u.un_text
        ORDER BY u.un_text
        """,
        region_id,
        YEAR,
    )
    region = await fetchrow(
        "SELECT region_name FROM regions WHERE region_id=$1", region_id
    )
    if region is None:
        raise HTTPException(404, "Hudud topilmadi")
    return {
        "region": region["region_name"],
        "universities": [
            {
                **dict(r),
                "min_ball": float(r["min_ball"]) if r["min_ball"] is not None else None,
                "max_ball": float(r["max_ball"]) if r["max_ball"] is not None else None,
            }
            for r in rows
        ],
    }


@app.get("/api/university/{un_id}")
async def university(un_id: str):
    info = await fetchrow(
        """
        SELECT u.un_id, u.un_text AS name, r.region_name AS region
        FROM universities u JOIN regions r ON u.region_id = r.region_id
        WHERE u.un_id = $1
        """,
        un_id,
    )
    if info is None:
        raise HTTPException(404, "OTM topilmadi")
    rows = await fetch(
        """
        SELECT mvdir, nomi, ty_id, lan_id,
               ROUND(con_b::numeric,1) AS ball,
               ROUND(gr_b::numeric,1)  AS grand_ball
        FROM mandat WHERE un_id = $1 AND year = $2
        ORDER BY nomi, ty_id, lan_id
        """,
        un_id,
        YEAR,
    )
    directions = [
        {
            "mvdir": r["mvdir"],
            "nomi": r["nomi"],
            "ty_id": r["ty_id"],
            "ty": _ty(r["ty_id"]),
            "lan_id": r["lan_id"],
            "lan": _lan(r["lan_id"]),
            "ball": float(r["ball"]),
            "grand_ball": float(r["grand_ball"]),
        }
        for r in rows
    ]
    types = sorted({(d["ty_id"], d["ty"]) for d in directions})
    langs = sorted({(d["lan_id"], d["lan"]) for d in directions})
    return {
        **dict(info),
        "types": [{"id": t[0], "name": t[1]} for t in types],
        "langs": [{"id": l[0], "name": l[1]} for l in langs],
        "directions": directions,
    }


@app.get("/api/directions")
async def directions(q: str = ""):
    qn = norm_query(q)
    norm_nomi = SQL_NORM.format(col="nomi")
    where = f"WHERE year = $1 AND {norm_nomi} LIKE $2" if qn else "WHERE year = $1"
    args = [YEAR, f"%{qn}%"] if qn else [YEAR]
    rows = await fetch(
        f"""
        SELECT nomi, COUNT(DISTINCT un_id) AS unis,
               ROUND(MIN(con_b) FILTER (WHERE con_b>0)::numeric,1) AS min_ball
        FROM mandat {where}
        GROUP BY nomi ORDER BY nomi
        """,
        *args,
    )
    return [
        {
            "nomi": r["nomi"],
            "unis": r["unis"],
            "min_ball": float(r["min_ball"]) if r["min_ball"] is not None else None,
        }
        for r in rows
    ]


@app.get("/api/direction")
async def direction(nomi: str):
    rows = await fetch(
        """
        SELECT m.un_id, u.un_text, r.region_name AS region,
               m.ty_id, m.lan_id, m.mvdir,
               ROUND(m.con_b::numeric,1) AS ball,
               ROUND(m.gr_b::numeric,1)  AS grand_ball
        FROM mandat m
        JOIN universities u ON m.un_id = u.un_id
        JOIN regions r ON m.region_id = r.region_id
        WHERE m.nomi = $1 AND m.year = $2
        ORDER BY CASE WHEN m.con_b > 0 THEN 0 ELSE 1 END, m.con_b ASC
        """,
        nomi,
        YEAR,
    )
    if not rows:
        raise HTTPException(404, "Yo'nalish topilmadi")
    return {
        "nomi": nomi,
        "offers": [
            {
                "un_id": r["un_id"],
                "un_text": r["un_text"],
                "region": r["region"],
                "ty": _ty(r["ty_id"]),
                "lan": _lan(r["lan_id"]),
                "mvdir": r["mvdir"],
                "ball": float(r["ball"]),
                "grand_ball": float(r["grand_ball"]),
            }
            for r in rows
        ],
    }


@app.get("/api/by-score")
async def by_score(
    ball: float = Query(..., ge=0, le=200),
    region_id: int | None = None,
    ty_id: str | None = None,
    limit: int = Query(100, le=300),
    offset: int = 0,
):
    conds = ["m.year = $1", "m.con_b > 0", "m.con_b <= $2"]
    args: list = [YEAR, ball]
    if region_id is not None:
        args.append(region_id)
        conds.append(f"m.region_id = ${len(args)}")
    if ty_id:
        args.append(ty_id)
        conds.append(f"m.ty_id = ${len(args)}")
    where = " AND ".join(conds)

    total = await fetchrow(f"SELECT COUNT(*) AS n FROM mandat m WHERE {where}", *args)
    args_page = [*args, limit, offset]
    rows = await fetch(
        f"""
        SELECT m.un_id, u.un_text, r.region_name AS region, m.nomi, m.mvdir,
               m.ty_id, m.lan_id, ROUND(m.con_b::numeric,1) AS ball
        FROM mandat m
        JOIN universities u ON m.un_id = u.un_id
        JOIN regions r ON m.region_id = r.region_id
        WHERE {where}
        ORDER BY m.con_b DESC
        LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}
        """,
        *args_page,
    )
    return {
        "total": total["n"],
        "items": [
            {
                "un_id": r["un_id"],
                "un_text": r["un_text"],
                "region": r["region"],
                "nomi": r["nomi"],
                "mvdir": r["mvdir"],
                "ty": _ty(r["ty_id"]),
                "lan": _lan(r["lan_id"]),
                "ball": float(r["ball"]),
            }
            for r in rows
        ],
    }


@app.get("/api/search")
async def search(q: str):
    qn = norm_query(q)
    if len(qn) < 2:
        return {"universities": [], "directions": []}
    like = f"%{qn}%"
    norm_un = SQL_NORM.format(col="u.un_text")
    norm_nomi = SQL_NORM.format(col="nomi")
    unis = await fetch(
        f"""
        SELECT u.un_id, u.un_text AS name, r.region_name AS region,
               COUNT(m.id) AS dirs
        FROM universities u
        JOIN regions r ON u.region_id = r.region_id
        LEFT JOIN mandat m ON m.un_id = u.un_id AND m.year = $1
        WHERE {norm_un} LIKE $2
        GROUP BY u.un_id, u.un_text, r.region_name
        ORDER BY u.un_text LIMIT 10
        """,
        YEAR,
        like,
    )
    dirs = await fetch(
        f"""
        SELECT nomi, COUNT(DISTINCT un_id) AS unis,
               ROUND(MIN(con_b) FILTER (WHERE con_b>0)::numeric,1) AS min_ball
        FROM mandat
        WHERE year = $1 AND {norm_nomi} LIKE $2
        GROUP BY nomi ORDER BY nomi LIMIT 10
        """,
        YEAR,
        like,
    )
    return {
        "universities": [dict(r) for r in unis],
        "directions": [
            {
                "nomi": r["nomi"],
                "unis": r["unis"],
                "min_ball": float(r["min_ball"]) if r["min_ball"] is not None else None,
            }
            for r in dirs
        ],
    }


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<text y="0.9em" font-size="90">🎓</text></svg>'
    )
    from fastapi.responses import Response

    return Response(content=svg, media_type="image/svg+xml")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
