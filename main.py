from dotenv import dotenv_values
import requests
import webbrowser
import websocket
import json
import lib.utils
from lib.cell import Cell

import time
from collections import deque
from queue import PriorityQueue

FRONTEND_BASE = "goldrush.monad.fi"
BACKEND_BASE = "goldrush.monad.fi/backend"

game_id = None
cells = dict()
stack = list()
queue = deque()
shortest_path_found = False
previous_command = None
prio_queue = PriorityQueue()
costs = dict()
estimates = dict()

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

    # Assume backend serves correct game state.
    position = game_state['player']['position']
    target = game_state['target']
    rotation = game_state['player']['rotation']
    square = game_state['square']
    
    # Initialize algorithms.
    if len(cells) == 0:
        cells[(position['x'], position['y'])] = Cell( position['x'], position['y'] )
        prio_queue.put( (0, ( position['x'], position['y']) ) )
        costs[(position['x'], position['y'])] = 0
        estimates[(position['x'], position['y'])] = lib.utils.calculateDistance( (position['x'], position['y']), target )

    if shortest_path_found:
        action = traverse_path(position, target, rotation)
    else:
        # action = bfs(position, target, rotation, square)
        # action = dfs(position, target, rotation, square)
        action = a_star(position, target, rotation, square)
    print("action:", action)
    return action

def a_star(position, target, rotation, square):
    global shortest_path_found
    print("prio_queue:", prio_queue.queue)
    # To move forward in a_star, we need to be on the cell with the most potential.
    current_cell = ( position['x'], position['y'] )
    
    # Get next cell. Ignore cells that to which we have already discovered the shortest path.
    next_cell = prio_queue.get()
    while next_cell[0] > costs[next_cell[1]] + estimates[next_cell[1]]:
        next_cell = prio_queue.get()  # TODO: Make exception safe.
    print("target next_cell:", next_cell)
    if current_cell == next_cell[1]:
         # We are on the cell with the most potential, so we can proceed with the algorithm.

        # Initialize the neighbours if this is the first time visiting this cell.
        if len(cells[position['x'], position['y']].neighbours.keys()) == 0:
            walls = lib.utils.getWalls( square )
            neighbours = lib.utils.getNeighbours(position, target, walls)
            cells[(position['x'], position['y'])].set_neighbours( neighbours )
            create_neighbour_cells( neighbours, position, target )
        
        # Update estimates for neighbours.
        for neighbour_position, neighbour_rotation in cells[current_cell].neighbours.items():
            if neighbour_position == (target['x'], target['y']):
                print("SHORTEST PATH FOUND")
                shortest_path_found = True
                target_cell = Cell( target['x'], target['y'] )
                target_cell.set_previous_cell( (position['x'], position['y']) )
                cells[(target['x'], target['y'])] = target_cell
                return { "action": "reset" }

            cost_from_current = costs[current_cell] + 1
            if cost_from_current < costs[neighbour_position]:
                costs[neighbour_position] = cost_from_current
                prio_queue.put( (cost_from_current + estimates[neighbour_position], neighbour_position) )
                cells[neighbour_position].set_previous_cell( current_cell )
    
    # We are not on the right cell for the algorithm, so put the cell back in the queue for now.
    else:
        prio_queue.put( next_cell )
    
    # we need to move to the next cell to proceed with algorithm.
    print("prio_queue:", prio_queue.queue)
    next_cell = prio_queue.queue[0][1]

    # Check for next cell in current cell's neighbours. This might save time as next cell is likely to be a neighbour.
    for neighbour_position, neighbour_rotation in cells[current_cell].neighbours.items():
        if neighbour_position == next_cell and rotation == cells[current_cell].neighbours[neighbour_position]:
            return { "action": "move" }
        # Next cell was found in neighbours but the rotation is incorrect -> rotate.
        if neighbour_position == next_cell:
            return { "action": "rotate", "rotation": cells[current_cell].neighbours[neighbour_position] }

    print("current_cell:", current_cell)
    print("next_cell:", next_cell)

    # Find common ancestor in order to eventually find the next cell.
    common_ancestor = findCommonAncestor( cells[current_cell], cells[next_cell] )
    print("common_ancestor", common_ancestor.x, common_ancestor.y)

    # Need to go backwards to get to common ancestor. Could probably search for a better path towards next cell here.
    if (common_ancestor.x, common_ancestor.y) != current_cell:
        previous_cell_rotation = cells[current_cell].neighbours[cells[current_cell].previous_cell]
        if rotation == previous_cell_rotation:
            return { "action": "move" }
        else:
            return { "action": "rotate", "rotation": previous_cell_rotation }

    # Current cell is the common ancestor, so we can traverse the path to the next cell.
    else:
        # Find neighbouring cell that will take us towards the next cell.
        while cells[next_cell].previous_cell != current_cell:
            next_cell = cells[next_cell].previous_cell
        new_target_rotation = cells[current_cell].neighbours[next_cell]
        if rotation == new_target_rotation:
            return { "action": "move" }
        else:
            return { "action": "rotate", "rotation": new_target_rotation }


# Traverses the found path from the current position to the target.
def traverse_path(position, target, rotation):
    target = cells[(target['x'], target['y'])]
    while target.previous_cell != (position['x'], position['y']):
        target = cells[target.previous_cell]
    if rotation != cells[(position['x'], position['y'])].neighbours[(target.x, target.y)]:
        return { "action": "rotate", "rotation": cells[(position['x'], position['y'])].neighbours[(target.x, target.y)] }
    else:
        return { "action": "move" }


def create_neighbour_cells(neighbours, position, target={'x': 999999, 'y': 999999}):
    for pos, rotation in neighbours.items():
        if not pos in cells:
            new_cell = Cell( pos[0], pos[1], lib.utils.calculateDistance( pos, target ) )
            new_cell.set_previous_cell( (position["x"], position["y"]) )
            cells[pos] = new_cell
            costs[pos] = costs[(position["x"], position["y"])] + 1
            estimates[pos] = lib.utils.calculateDistance( pos, target )
            prio_queue.put( (costs[pos] + estimates[pos], pos) )


# Finds common ancestor of two cells. Probably not the most efficient way to do this.
def findCommonAncestor(a, b):
    a_ancestors = []
    if a.previous_cell is None:
        return a
    
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