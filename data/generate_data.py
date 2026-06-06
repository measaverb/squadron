#!/usr/bin/env python3
"""
Squadron — synthetic dataset generator
=======================================
Generates a reproducible, fully synthetic dataset for the "Squadron" engineering
resource-manager prototype (algorithms final project, team of four).

The data is SYNTHETIC, but its parameters are grounded in real open sources, and
both facts are declared (requirement 4: Input data + source):
  * Skill/technology popularity and the seniority spread are modelled on the
    Stack Overflow Annual Developer Survey  (https://survey.stackoverflow.co/).
  * Task titles and effort estimates follow conventions seen in public issue
    trackers such as the Apache Software Foundation Jira
    (https://issues.apache.org/).
Every record is generated locally; no real personal or proprietary data is used.

Run:
    python generate_data.py                      # writes ./data with the default seed
    python generate_data.py --seed 7 --out ./data

Outputs (JSON unless noted):
    projects.json       projects   (id, name, description, deadline)
    sprints.json        sprints    (id, project, capacity)
    developers.json     55 developer trait profiles
    developers.csv      the same, tabular (for teammates who prefer a spreadsheet)
    tasks.json          the backlog as a DAG (depends_on edges; always acyclic)
    tasks_broken.json   identical, plus ONE injected back-edge (a cycle) for the
                        dependency-resolver's cycle-detection demonstration
    README.md           data dictionary + sources + the engineered demo cases

No external libraries required (Python 3.8+ standard library only).
"""

import argparse
import csv
import json
import random
from collections import defaultdict, deque
from datetime import date, timedelta
from pathlib import Path

# -----------------------------------------------------------------------------
# Configuration (defaults; --seed and --out override on the CLI)
# -----------------------------------------------------------------------------
SEED = 42
NUM_DEVELOPERS = 55          # > 50, as required
TASKS_PER_PROJECT = 50       # ~150 tasks across three projects
SPRINTS_PER_PROJECT = 4

# (id, name, description, dominant skill categories the project's tasks draw from)
PROJECTS = [
    ("P1", "Apollo",   "Payments and billing platform",       ["backend", "data", "devops"]),
    ("P2", "Borealis", "Customer-facing mobile application",  ["mobile", "frontend", "backend"]),
    ("P3", "Cirrus",   "Internal data and analytics platform",["data", "devops", "backend"]),
]

# skill -> (category, popularity weight). Higher weight = more common, mirroring
# the relative technology-usage ranking in the Stack Overflow survey.
SKILL_CATALOGUE = {
    "javascript": ("frontend", 10), "typescript": ("frontend", 8),
    "react": ("frontend", 9), "vue": ("frontend", 4),
    "html_css": ("frontend", 9), "nextjs": ("frontend", 5),
    "python": ("backend", 10), "java": ("backend", 8), "nodejs": ("backend", 8),
    "go": ("backend", 5), "csharp": ("backend", 5), "ruby": ("backend", 3),
    "rust": ("backend", 2),
    "sql": ("data", 10), "postgresql": ("data", 6), "mongodb": ("data", 5),
    "pandas": ("data", 6), "airflow": ("data", 3), "spark": ("data", 2),
    "docker": ("devops", 8), "aws": ("devops", 8), "cicd": ("devops", 6),
    "kubernetes": ("devops", 5), "terraform": ("devops", 2),
    "kotlin": ("mobile", 5), "swift": ("mobile", 3), "flutter": ("mobile", 2),
}

# Deliberately scarce skills: withheld from the common draw and handed to only a
# few developers, while several tasks demand them. This scarcity is what lets the
# Hungarian allocator's GLOBAL optimum beat a greedy one (see README.md).
RARE_SKILLS = ["rust", "spark", "terraform", "flutter"]
HOLDERS_PER_RARE_SKILL = 3

COMMON_SKILLS = [s for s in SKILL_CATALOGUE if s not in RARE_SKILLS]
COMMON_WEIGHTS = [SKILL_CATALOGUE[s][1] for s in COMMON_SKILLS]
ALL_CATEGORIES = sorted({c for _s, (c, _w) in SKILL_CATALOGUE.items()})

FIRST_NAMES = ["Min", "Ji", "Soo", "Hyun", "Jun", "Yuna", "Seo", "Hana",
               "Alex", "Sam", "Wei", "Chen", "Aditi", "Omar", "Maria", "Liam",
               "Noah", "Emma", "Yuki", "Hiro", "Sofia", "Ivan", "Priya", "Tariq",
               "Lena", "Diego", "Mei", "Jin", "Ravi", "Nora"]
LAST_NAMES  = ["Kim", "Lee", "Park", "Choi", "Jung", "Kang", "Cho", "Yoon",
               "Smith", "Chen", "Wang", "Patel", "Garcia", "Muller", "Rossi",
               "Tanaka", "Nguyen", "Khan", "Silva", "Novak", "Andersson",
               "Okafor", "Haddad", "Reyes", "Singh", "Costa", "Ito", "Petrov",
               "Dubois", "Bauer"]

TASK_TEMPLATES = {
    "frontend": ["Build {n} screen", "Redesign {n} component", "Add {n} to the UI",
                 "Fix {n} rendering bug", "Implement {n} form"],
    "backend":  ["Implement {n} endpoint", "Refactor {n} service", "Add {n} API",
                 "Optimise {n} query path", "Write {n} business logic"],
    "data":     ["Build {n} pipeline", "Model {n} schema", "Add {n} ETL job",
                 "Create {n} dashboard", "Migrate {n} table"],
    "devops":   ["Set up {n} infrastructure", "Automate {n} deployment",
                 "Add {n} monitoring", "Containerise {n}", "Configure {n} pipeline"],
    "mobile":   ["Build {n} screen", "Add {n} flow", "Fix {n} crash",
                 "Implement {n} offline sync", "Optimise {n} startup"],
}
NOUNS = ["login", "checkout", "payment", "profile", "search", "notification",
         "dashboard", "settings", "onboarding", "billing", "report", "auth",
         "cart", "feed", "messaging", "analytics", "export", "import",
         "scheduler", "wallet", "catalogue", "inventory", "session", "audit"]

# effort estimate (story points) sampled by difficulty, on a Fibonacci-ish scale
EST_BY_DIFFICULTY = {1: [1, 2], 2: [2, 3], 3: [3, 5], 4: [5, 8], 5: [8, 13]}


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------
def skills_in(category):
    return [s for s, (c, _w) in SKILL_CATALOGUE.items() if c == category]


def unique_names(n):
    seen, out = set(), []
    while len(out) < n:
        pair = (random.choice(FIRST_NAMES), random.choice(LAST_NAMES))
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out


def weighted_sample_without_replacement(items, weights, k):
    items, weights, chosen = list(items), list(weights), []
    for _ in range(min(k, len(items))):
        i = random.choices(range(len(items)), weights=weights)[0]
        chosen.append(items.pop(i))
        weights.pop(i)
    return chosen


# -----------------------------------------------------------------------------
# Entity generation
# -----------------------------------------------------------------------------
def build_projects(start=date(2025, 9, 1)):
    projects = []
    for i, (pid, name, desc, _cats) in enumerate(PROJECTS):
        deadline = start + timedelta(weeks=8 + i * 4)   # staggered deadlines
        projects.append({"id": pid, "name": name,
                         "description": desc, "deadline": deadline.isoformat()})
    return projects


def build_developers():
    """50+ developers. Skills are drawn by popularity but biased toward each
    person's primary category, so profiles stay coherent (a 'react + html_css'
    front-ender, not a random scatter). Rare skills are placed by hand."""
    names = unique_names(NUM_DEVELOPERS)

    # Pre-pick the holders of each rare skill so scarcity is exact, not random.
    rare_holders = defaultdict(set)          # dev_index -> {rare skills}
    rare_by_skill = {}                       # rare skill -> [dev ids]
    for skill in RARE_SKILLS:
        holders = random.sample(range(NUM_DEVELOPERS), HOLDERS_PER_RARE_SKILL)
        rare_by_skill[skill] = [f"D{h+1:03d}" for h in holders]
        for h in holders:
            rare_holders[h].add(skill)

    level_choices = [1, 2, 3, 4, 5]
    level_weights = [15, 30, 30, 18, 7]      # mid-weighted seniority spread

    devs = []
    for idx in range(NUM_DEVELOPERS):
        level = random.choices(level_choices, weights=level_weights)[0]
        n_skills = min(len(COMMON_SKILLS), 2 + level + random.randint(0, 2))

        primary = random.choice(ALL_CATEGORIES)
        weights = [w * (3 if SKILL_CATALOGUE[s][0] == primary else 1)
                   for s, w in zip(COMMON_SKILLS, COMMON_WEIGHTS)]
        skills = set(weighted_sample_without_replacement(COMMON_SKILLS, weights, n_skills))
        skills |= rare_holders.get(idx, set())

        capacity = 28 + level * 3 + random.randint(0, 6)         # ~31-49 points
        current_load = random.randint(0, int(capacity * 0.6))
        familiar = random.sample([p[0] for p in PROJECTS], random.randint(1, 2))

        first, last = names[idx]
        devs.append({
            "id": f"D{idx + 1:03d}",
            "name": f"{first} {last}",
            "level": level,
            "skills": sorted(skills),
            "capacity": capacity,
            "current_load": current_load,
            "familiar_projects": sorted(familiar),
        })
    return devs, rare_by_skill


def build_tasks():
    """One backlog per project. Dependencies are added as a DAG: a task may only
    depend on EARLIER-indexed tasks, which guarantees the graph is acyclic."""
    tasks, counter = [], 1
    for pid, name, _desc, cats in PROJECTS:
        project_tasks = []
        for _ in range(TASKS_PER_PROJECT):
            cat = random.choice(cats)
            title = random.choice(TASK_TEMPLATES[cat]).format(n=random.choice(NOUNS))
            pool = [s for s in skills_in(cat) if s not in RARE_SKILLS]
            req = random.sample(pool, random.randint(1, min(3, len(pool))))
            difficulty = random.choices([1, 2, 3, 4, 5], weights=[15, 25, 30, 20, 10])[0]

            project_tasks.append({
                "id": f"T{counter:04d}", "project": pid, "title": title,
                "description": f"{title} for the {name} project.",
                "tags": sorted(set([cat] + title.lower().split()[1:2])),
                "required_skills": sorted(req),
                "difficulty": difficulty,
                "estimate": random.choice(EST_BY_DIFFICULTY[difficulty]),
                "value": random.randint(10, 100),
                "priority": random.choices([1, 2, 3, 4], weights=[15, 30, 35, 20])[0],
                "depends_on": [], "sprint": None, "assignee": None,
            })
            counter += 1
        _add_dag_edges(project_tasks)
        tasks.extend(project_tasks)
    return tasks


def _add_dag_edges(project_tasks):
    """Each task takes 0-2 prerequisites from a recent window of earlier tasks."""
    ids = [t["id"] for t in project_tasks]
    for i in range(len(project_tasks)):
        max_preds = 2 if i > 3 else (1 if i > 0 else 0)
        n_preds = random.randint(0, max_preds)
        if n_preds and i > 0:
            candidates = list(range(max(0, i - 8), i))
            for p in random.sample(candidates, min(n_preds, len(candidates))):
                project_tasks[i]["depends_on"].append(ids[p])


# -----------------------------------------------------------------------------
# Engineered demonstration cases  (so the algorithms have something to show)
# -----------------------------------------------------------------------------
def engineer_critical_chain(tasks):
    """Force a long, heavy dependency chain through the first 8 tasks of P1 so the
    critical path (longest path in the DAG) is clearly non-trivial to compute."""
    chain = [t for t in tasks if t["project"] == "P1"][:8]
    for i, t in enumerate(chain):
        t["depends_on"] = [] if i == 0 else [chain[i - 1]["id"]]
        t["estimate"] = 13 if i % 2 == 0 else 8        # 13+8+...+8 = 84-point spine
        t["difficulty"] = 5
        t["title"] = f"[Critical] {t['title']}"
    return [t["id"] for t in chain]


def inject_rare_skill_demand(tasks, per_skill=3):
    """Make several tasks REQUIRE the scarce skills, creating contention that a
    greedy allocator handles worse than the Hungarian (global) one."""
    cat_of = {s: c for s, (c, _w) in SKILL_CATALOGUE.items()}
    proj_cats = {p[0]: p[3] for p in PROJECTS}
    injected = defaultdict(list)
    for skill in RARE_SKILLS:
        candidates = [t for t in tasks
                      if cat_of[skill] in proj_cats[t["project"]]
                      and skill not in t["required_skills"]]
        for t in random.sample(candidates, min(per_skill, len(candidates))):
            t["required_skills"] = sorted(set(t["required_skills"]) | {skill})
            injected[skill].append(t["id"])
    return injected


def assign_sprints(tasks):
    """Bucket each project's tasks into sprints by dependency DEPTH (longest chain
    ending at the task), so prerequisites naturally fall into earlier sprints.
    Sprint capacity is set to ~60% of its tasks' total estimate, forcing the
    sprint planner to actually choose a subset rather than take everything."""
    by_project = defaultdict(list)
    for t in tasks:
        by_project[t["project"]].append(t)

    sprints = []
    for pid, ptasks in by_project.items():
        depth = {}
        for t in ptasks:        # ptasks are in id order == a valid topological order
            depth[t["id"]] = 1 + max((depth[p] for p in t["depends_on"]), default=0)
        max_d = max(depth.values())
        for t in ptasks:
            s = min(SPRINTS_PER_PROJECT,
                    1 + (depth[t["id"]] - 1) * SPRINTS_PER_PROJECT // max_d)
            t["sprint"] = f"{pid}-S{s}"
        for k in range(1, SPRINTS_PER_PROJECT + 1):
            sprints.append({"id": f"{pid}-S{k}", "project": pid, "capacity": 0})
    for s in sprints:
        _recompute_capacity(tasks, sprints, s["id"])
    return sprints


def _recompute_capacity(tasks, sprints, sid):
    members = [t for t in tasks if t["sprint"] == sid]
    total = sum(t["estimate"] for t in members)
    mx = max((t["estimate"] for t in members), default=1)
    cap = max(mx, round(0.6 * total)) if members else mx
    for s in sprints:
        if s["id"] == sid:
            s["capacity"] = cap


def engineer_knapsack_counterexample(tasks, sprints):
    """Plant a textbook 0/1-knapsack counterexample in one isolated sprint:
    capacity 10 with items A(6,60), B(5,40), C(5,40). Greedy by value-density
    takes A (60) and cannot fit anything else; the optimum is B+C (80)."""
    demo_sid = "P3-S4"
    for t in tasks:                              # clear the sprint, push to P3-S3
        if t["sprint"] == demo_sid:
            t["sprint"] = "P3-S3"
    next_id = len(tasks) + 1
    ids = []
    for label, est, val in [("A", 6, 60), ("B", 5, 40), ("C", 5, 40)]:
        tid = f"T{next_id:04d}"
        tasks.append({
            "id": tid, "project": "P3",
            "title": f"[Demo] Knapsack item {label}",
            "description": "Planted sprint-planner demo task (see README.md).",
            "tags": ["demo", "backend"], "required_skills": ["python"],
            "difficulty": 3, "estimate": est, "value": val,
            "priority": 2, "depends_on": [], "sprint": demo_sid, "assignee": None,
        })
        ids.append(tid)
        next_id += 1
    _recompute_capacity(tasks, sprints, "P3-S3")
    for s in sprints:
        if s["id"] == demo_sid:
            s["capacity"] = 10
    return ids, demo_sid


def make_broken(tasks, critical_ids):
    """A copy of the backlog with ONE back-edge added (head depends on tail of the
    critical chain), producing a cycle for the resolver's cycle detector to catch."""
    broken = json.loads(json.dumps(tasks))       # deep copy
    head, tail = critical_ids[0], critical_ids[-1]
    for t in broken:
        if t["id"] == head:
            t["depends_on"] = sorted(set(t["depends_on"]) | {tail})
    return broken


# -----------------------------------------------------------------------------
# Validation (self-check) + writers
# -----------------------------------------------------------------------------
def is_acyclic(tasks):
    indeg, adj, ids = defaultdict(int), defaultdict(list), set()
    for t in tasks:
        ids.add(t["id"])
        for p in t["depends_on"]:
            adj[p].append(t["id"])
            indeg[t["id"]] += 1
    q = deque(i for i in ids if indeg[i] == 0)
    seen = 0
    while q:
        n = q.popleft()
        seen += 1
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    return seen == len(ids)


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def write_developers_csv(path, devs):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "level", "skills", "capacity",
                    "current_load", "familiar_projects"])
        for d in devs:
            w.writerow([d["id"], d["name"], d["level"], ";".join(d["skills"]),
                        d["capacity"], d["current_load"], ";".join(d["familiar_projects"])])


def write_readme(path, seed, n_dev, n_task, projects, sprints,
                 rare_by_skill, rare_injected, critical_ids, knap_ids, demo_sid):
    demo_cap = next(s["capacity"] for s in sprints if s["id"] == demo_sid)
    holders = "\n".join(f"  - `{s}`: held by {', '.join(rare_by_skill[s])}; "
                        f"demanded by {', '.join(rare_injected[s])}" for s in RARE_SKILLS)
    md = f"""# Squadron — synthetic dataset

A fully synthetic dataset for the **Squadron** engineering resource-manager
prototype. Generated by `generate_data.py` with seed `{seed}`; the same seed
reproduces this dataset exactly.

## Provenance and sources
All records are generated programmatically — no real personal or proprietary data
is used. The generator's *parameters* are nonetheless grounded in real open data:

- **Skill/technology popularity** and the **seniority distribution** are modelled
  on the Stack Overflow Annual Developer Survey — https://survey.stackoverflow.co/
- **Task titles and effort estimates** follow conventions in public issue trackers
  such as the Apache Software Foundation Jira — https://issues.apache.org/

## Files
- `projects.json` — {len(projects)} projects (`id`, `name`, `description`, `deadline`)
- `sprints.json` — {len(sprints)} sprints (`id`, `project`, `capacity` in story points)
- `developers.json` — {n_dev} developer trait profiles
- `developers.csv` — the same, tabular
- `tasks.json` — {n_task} tasks; dependency graph is a **DAG** (always acyclic)
- `tasks_broken.json` — identical, plus one injected cycle (cycle-detection demo)

## Field dictionary
**developer**: `id`, `name`, `level` (1 junior – 5 principal), `skills` (list),
`capacity` (story points per sprint), `current_load` (points already committed),
`familiar_projects` (list of project ids).

**task**: `id`, `project`, `title`, `description`, `tags` (list), `required_skills`
(list), `difficulty` (1–5), `estimate` (story points), `value` (business value
10–100), `priority` (1 highest – 4 lowest), `depends_on` (list of prerequisite
task ids), `sprint` (sprint id), `assignee` (`null`; filled by the allocator).

## Engineered demonstration cases
These are planted deliberately so each algorithm has an instructive instance to
show in the report and the video.

1. **Critical path (longest path in a DAG).** A heavy dependency chain runs through
   the first eight P1 tasks: `{', '.join(critical_ids)}` (estimates 13/8 alternating,
   an 84-point spine). The critical path should run straight through these.

2. **Sprint-planner counterexample (0/1 knapsack).** Sprint `{demo_sid}` has capacity
   `{demo_cap}` and contains items `{', '.join(knap_ids)}` = A(6,60), B(5,40), C(5,40).
   Greedy by value-density takes A (value 60) and can fit nothing else; the optimum
   is B+C (value 80). This exhibits the greedy/optimal gap.

3. **Allocator scarcity (Hungarian vs greedy).** Four skills are scarce — each held
   by only {HOLDERS_PER_RARE_SKILL} developers — yet demanded by several tasks:
{holders}
   Because the scarce-skill holders are also attractive for ordinary tasks, a greedy
   (priority-ordered) allocation can consume a holder on a task that did not need
   them, leaving a scarce-skill task unstaffed; the Hungarian algorithm avoids this
   by optimising the assignment globally.

## Reproducibility
`python generate_data.py --seed {seed}` regenerates this dataset byte-for-byte.
No external libraries are required (Python 3.8+ standard library only).
"""
    path.write_text(md, encoding="utf-8")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Generate the Squadron synthetic dataset.")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()

    random.seed(args.seed)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    projects = build_projects()
    developers, rare_by_skill = build_developers()
    tasks = build_tasks()

    critical_ids = engineer_critical_chain(tasks)
    rare_injected = inject_rare_skill_demand(tasks)
    sprints = assign_sprints(tasks)
    knap_ids, demo_sid = engineer_knapsack_counterexample(tasks, sprints)

    # self-check: the backlog is acyclic; the broken variant is not
    assert is_acyclic(tasks), "tasks.json should be acyclic but is not"
    tasks_broken = make_broken(tasks, critical_ids)
    assert not is_acyclic(tasks_broken), "tasks_broken.json should contain a cycle"

    write_json(out / "projects.json", projects)
    write_json(out / "sprints.json", sprints)
    write_json(out / "developers.json", developers)
    write_developers_csv(out / "developers.csv", developers)
    write_json(out / "tasks.json", tasks)
    write_json(out / "tasks_broken.json", tasks_broken)
    write_readme(out / "README.md", args.seed, len(developers), len(tasks),
                 projects, sprints, rare_by_skill, rare_injected,
                 critical_ids, knap_ids, demo_sid)

    # ---- summary ----
    print(f"Squadron dataset written to {out.resolve()}  (seed={args.seed})")
    print(f"  developers : {len(developers)}")
    print(f"  projects   : {len(projects)}  ({', '.join(p['id'] for p in projects)})")
    print(f"  sprints    : {len(sprints)}")
    print(f"  tasks      : {len(tasks)}  (acyclic: {is_acyclic(tasks)})")
    print(f"  broken     : cycle present = {not is_acyclic(tasks_broken)}")
    print("  engineered cases:")
    print(f"    - critical chain (P1)      : {' -> '.join(critical_ids)}")
    print(f"    - knapsack demo ({demo_sid}, cap "
          f"{next(s['capacity'] for s in sprints if s['id'] == demo_sid)}): "
          f"{', '.join(knap_ids)}")
    for s in RARE_SKILLS:
        print(f"    - scarce '{s}': holders {rare_by_skill[s]}  "
              f"demanded by {rare_injected[s]}")


if __name__ == "__main__":
    main()
