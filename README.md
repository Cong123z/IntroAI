# Vienna subway Navigator 

This app lets you find the fastest route around Vienna's subway system.
You pick a start and end point on a map, and it shows you exactly where to walk,
which train to take, and where to transfer.

## Step 1 — Set up the project

Open a terminal, go to the project folder, then run these three commands:

```
python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt
```

*(Downloads all the libraries the project needs — only needed once)*

---

## Step 2 — Download the map data

Run these three commands once — they download and prepare the data files:

```
python scripts/download_gtfs.py

python scripts/download_walk_osm.py

python scripts/build_graph.py
```

## Step 3 — Start the app

```
uvicorn backend.app.main:app --reload --port 8000
```
INFO:     Application startup complete.
Then open your browser and go to:
```

- http://localhost:8000 — the main app (plan your route here)
- http://localhost:8000/admin.html — function panel (simulate disruptions)

```

## How to use the main app
<img width="1918" height="863" alt="image" src="https://github.com/user-attachments/assets/75de1bf9-d95c-4b6e-9115-de5e191d67a1" />

**Finding a route:**
1. Pick your start — either choose from the station list, or click " Pick on map" and click anywhere on the map
2. Pick your destination the same way
3. Click **Find Route**
4. Your route appears on the map as a coloured line, and the steps are listed on the left
**What the steps mean:**
- 🚶 Walk — go on foot to or from a station
- ⬇️ Enter — go into the station
- 🚇 Ride — sit on the train
- 🔄 Transfer — change to a different line at the same station
- ⬆️ Exit — leave the station

---

## How to use the function panel
<img width="1232" height="826" alt="image" src="https://github.com/user-attachments/assets/6dd5843c-2815-4828-b396-3c1d847e2f95" />

The function panel lets you control the simulation by adding network closures, changing the weather, and toggling visible map components.

**Map Display Settings:**
This section allows you to customize which components are visible on the map.

1. Subway Lines: Toggle this to show or hide the subway lines on the map.

2. Map Limits: Toggle this to show or hide the map boundaries.

Click the map link at the bottom of the panel to see your changes applied in real-time.

**Close a station, line, or segment:**
1. Choose what type of closure from the first dropdown (Station / Line / Segment)
2. Choose the specific station/line/segment from the second dropdown
3. Click **Add Closure**

Now go back to the main app and search for a route — it will automatically avoid
whatever you closed.

**Change the weather:**
Click ☀️ Clear, 🌧️ Rain, or ❄️ Snow. This changes how fast the app assumes you walk.

☀️ Clear - 1.4 m/s 

🌧️ Rain  - 1.1 m/s 

❄️ Snow  - 0.8 m/s 

**To remove a closure:** click the ✕ next to it in the list.

**To remove all closures at once:** click **Clear All**.

---


```
