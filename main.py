from dotenv import dotenv_values
import requests
import webbrowser
import websocket
import json
# from lib.math import normalize_heading, calc_straight_route, calc_turn, calc_airport_approach, calc_airport_target, calc_dist_to_airport
import lib.walls
import lib.neighbours
from lib.cell import Cell
import lib.algorithm
import time
from collections import deque

FRONTEND_BASE = "goldrush.monad.fi"
BACKEND_BASE = "goldrush.monad.fi/backend"

game_id = None
cells = dict()
#stack = list()
queue = deque()
shortest_path_found = False
previous_command = None

def on_message(ws: websocket.WebSocketApp, message):
    [action, payload] = json.loads(message)

    if action != "game-instance":
        print([action, payload])
        return

     # New game tick arrived!
    game_state = json.loads(payload["gameState"])
    commands = generate_commands(game_state)

    time.sleep(0.1)
    ws.send(json.dumps(["run-command", {"gameId": game_id, "payload": commands}]))


def on_error(ws: websocket.WebSocketApp, error):
    print(error)


def on_open(ws: websocket.WebSocketApp):
    print("OPENED")
    ws.send(json.dumps(["sub-game", {"id": game_id}]))


def on_close(ws, close_status_code, close_msg):
    print("CLOSED")

def generate_commands(game_state):
    print(game_state)
    global previous_command
    # Assume backend serves correct game state.
    position = game_state['player']['position']
    target = game_state['target']
    rotation = game_state['player']['rotation']
    square = game_state['square']
    
    # Add starting cell to cells.
    if len(cells) == 0:
        cells[(position['x'], position['y'])] = Cell( position['x'], position['y'] )

    if shortest_path_found:
        action = traverse_shortest_path(position)
    else:
        action = bfs(position, target, rotation, square)
    
    return action

'''
Implements a breadth-first search algorithm to find the shortest path to the target. Should be fine for small mazes.
'''
def bfs(position, target, rotation, square):
    # Get neighbours for a cell if this is the first time visiting it.
    if len(cells[position['x'], position['y']].neighbours.keys()) == 0:
        walls = lib.walls.getWalls( square )
        neighbours = lib.neighbours.getNeighbours(position, target, walls)
        cells[(position['x'], position['y'])].set_neighbours( neighbours )
        create_neighbour_cells( neighbours, position )
        queue.extend( neighbours.keys() )

    print("queue: ", queue)
    
    # If the next cell in queue has any neighbours, that means we have already visited that cell and can skip it.
    current_cell = cells[(position['x'], position['y'])]
    next_cell = None
    while len( cells[ queue[0] ].neighbours.keys() ) > 0:
        queue.popleft()
    next_cell = queue.popleft()

    print("current_cell:", current_cell.x, current_cell.y)
    print("next_cell:", next_cell)

    # Search current cell's neighbours for the next cell.
    for neighbour_position, neighbour_rotation in current_cell.neighbours.items():
        print("neighbour: ", neighbour_position, neighbour_rotation)
        # Target found, great! Reset to traverse the shortest path.
        if neighbour_position == (target['x'], target['y']):
            shortest_path_found = True
            target_cell = Cell( target['x'], target['y'] )
            target_cell.set_previous_cell( position )
            cells[(target['x'], target['y'])] = target_cell
            return { "action": "reset" }

        # Next cell was found in neighbours and the rotation is correct -> move.
        if neighbour_position == next_cell and rotation == current_cell.neighbours[neighbour_position]:
            return { "action": "move" }

        # Next cell was found in neighbours but the rotation is incorrect -> rotate.
        if neighbour_position == next_cell:
            queue.appendleft( next_cell )  # Add the cell back to the queue.
            return { "action": "rotate", "rotation": current_cell.neighbours[neighbour_position] }
        

    print("debug")
    # Next cell was not found in neighbours -> we might need to go backwards.
    # Add the cell back to the queue for now.
    queue.appendleft( next_cell )

    # Find common ancestor in order to eventually find the next cell.
    common_ancestor = findCommonAncestor( current_cell, cells[next_cell] )
    print("common_ancestor", common_ancestor.x, common_ancestor.y)
    # Need to go backwards to get to common ancestor.
    if common_ancestor != current_cell:
        previous_cell_rotation = current_cell.neighbours[current_cell.previous_cell]
        if rotation == previous_cell_rotation:
            return { "action": "move" }
        else:
            return { "action": "rotate", "rotation": previous_cell_rotation }

    # Current cell is the common ancestor, so we can traverse the path to the next cell.
    else:
        while cells[next_cell].previous_cell != (current_cell.x, current_cell.y):
            print("current_cell:", current_cell, "cells[next_cell].previous_cell:", cells[next_cell].previous_cell)
            next_cell = cells[next_cell].previous_cell
        new_target_rotation = current_cell.neighbours[next_cell]
        print("new_target_rotation:", new_target_rotation)
        if rotation == new_target_rotation:
            return { "action": "move" }
        else:
            return { "action": "rotate", "rotation": new_target_rotation }
    
    # If we get here, something went wrong.
    return None

def traverse_shortest_path(position, rotation):
    # Get target from path. There should always be at least 2 elements in the path at this stage.
    path.pop(0)
    target = path[0]
    
    for neighbour in cells[(position['x'], position['y'])].neighbours:
        if neighbour[0] == target and rotation == neighbour[2]:
            return { "action": "move" }
        if neighbour[0] == target and rotation != neighbour[2]:
            return { "action": "rotate", "rotation": neighbour[2] }
    
    # If we get here, something went wrong.
    return None

def create_neighbour_cells(neighbours, position):
    for pos, rotation in neighbours.items():
        if not pos in cells:
            new_cell = Cell( pos[0], pos[1] )
            new_cell.set_previous_cell( (position["x"], position["y"]) )
            cells[pos] = new_cell

# Finds common ancestor of two cells. Probably not the most efficient way to do this.
def findCommonAncestor(a, b):
    print("a", a, a.previous_cell)
    print("b", b)
    a_ancestors = []
    while a.previous_cell is not None:
        a_ancestors.append( (a.x, a.y) )
        a = cells[a.previous_cell]
    a_ancestors.append( (a.x, a.y) )  # Root cell has no previous cell, so add it manually.

    while b.previous_cell is not None:
        if (b.x, b.y) in a_ancestors:
            return cells[(b.x, b.y)]
        b = cells[b.previous_cell]
 

def main():
    config = dotenv_values()
    res = requests.post(
        f"https://{BACKEND_BASE}/api/levels/{config['LEVEL1_ID']}",
        headers={
            "Authorization": config["PLAYER_TOKEN"]
        })

    if not res.ok:
        print(f"Couldn't create game: {res.status_code} - {res.text}")
        return

    game_instance = res.json()

    global game_id
    game_id = game_instance["entityId"]

    url = f"https://{FRONTEND_BASE}/?id={game_id}"
    print(f"Game at {url}")
    webbrowser.open(url, new=2)
    time.sleep(2)

    ws = websocket.WebSocketApp(
        f"wss://{BACKEND_BASE}/{config['PLAYER_TOKEN']}/", on_message=on_message, on_open=on_open, on_close=on_close, on_error=on_error)
    ws.run_forever()


if __name__ == "__main__":
    main()