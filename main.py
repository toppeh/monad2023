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
path_optimized = False
previous_command = None
prio_queue = PriorityQueue()
costs = dict()
estimates = dict()
path = list()
distance_cost_factor = 1

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
    global path_optimized
    global path
    print("\n", game_state)

    # Assume backend serves correct game state.
    position = game_state['player']['position']
    position = ( position['x'], position['y'] )
    target = game_state['target']
    rotation = game_state['player']['rotation']
    square = game_state['square']
    
    # Initialize algorithms.
    if len(cells) == 0:
        cells[position] = Cell( position[0], position[1] )
        prio_queue.put( (0, position ) )
        costs[position] = 0
        estimates[position] = lib.utils.calculateDistance( position, target )

    # Decide what to do.
    if shortest_path_found:
        # Target has been found.
        if not path_optimized:
            # Form and optimize path from start to target.
            print("FORMING PATH")
            path = lib.utils.form_path( (target['x'], target['y']), cells, (game_state['start']['x'], game_state['start']['y']) )
            print("OPTIMIZING PATH")
            path = lib.utils.optimize_path( path, cells )
            path_optimized = True
            print("OPTIMIZING PATH DONE: ", path)

        # Travel the path to target cell.
        action = traverse_path(position, rotation, path)
    else:
        # Search for the target.
        # action = a_star(position, target, rotation, square)
        action = dfs(position, target, rotation, square)
    print("action:", action)
    return action

# Implements the A* algorithm.
def a_star(position, target, rotation, square):
    global shortest_path_found
    print("prio_queue:", prio_queue.queue)
    current_cell = ( position['x'], position['y'] )
    
    # Get next cell. Ignore cells that to which we have already discovered the shortest path.
    next_cell = prio_queue.get()
    while next_cell[0] > costs[next_cell[1]] + estimates[next_cell[1]]:
        next_cell = prio_queue.get()  # TODO: Make exception safe.
    print("target next_cell:", next_cell)

    # We need to check if we are on the right cell to continue with algorithm.
    if current_cell == next_cell[1]:
         # We are on the cell with the most potential, so we can proceed with the algorithm.

        # Initialize the neighbours if this is the first time visiting this cell (or if it's a dead end...).
        if len(cells[position['x'], position['y']].neighbours.keys()) <= 1:
            walls = lib.utils.getWalls( square )
            neighbours = lib.utils.getNeighbours(position, target, walls)
            if (position['x'], position['y']) == (2, 4):
                print("\n\nXDDDDDDD\n\n:", neighbours)
            cells[(position['x'], position['y'])].set_neighbours( neighbours )
            create_neighbour_cells( neighbours, position, target )
        
        # Update estimates for neighbours.
        for neighbour_position, neighbour_rotation in cells[current_cell].neighbours.items():
            # Target found, stop algorithm.
            if neighbour_position == (target['x'], target['y']):
                print("SHORTEST PATH FOUND")
                shortest_path_found = True
                target_cell = Cell( target['x'], target['y'] )
                target_cell.set_previous_cell( (position['x'], position['y']) )
                cells[(target['x'], target['y'])] = target_cell
                return { "action": "reset" }

            # Check cost from current cell to neighbour.
            cost_from_current = costs[current_cell] + 1
            if cost_from_current < costs[neighbour_position]:
                # Found a shorter path to this neighbour, update cell data.
                costs[neighbour_position] = cost_from_current
                prio_queue.put( (distance_cost_factor * cost_from_current + estimates[neighbour_position], neighbour_position) )
                cells[neighbour_position].set_previous_cell( current_cell )
    
    # We are not on the right cell for the algorithm, so put the cell back in the queue for now.
    else:
        prio_queue.put( next_cell )
    
    # We need to move to the next cell in prio queue to proceed with algorithm.
    print("prio_queue after algo:", prio_queue.queue)
    next_cell = prio_queue.queue[0][1]


    # Before searching for common ancestor between current cell and next cell check for next cell in current cell's neighbours.
    # This might save time as next cell is somewhat likely to be a neighbour.
    for neighbour_position, neighbour_rotation in cells[current_cell].neighbours.items():
        print("huijaus naapuri check", neighbour_position, "kohde", next_cell)
        if neighbour_position == next_cell and rotation == cells[current_cell].neighbours[neighbour_position]:
            return { "action": "move" }
        # Next cell was found in neighbours but the rotation is incorrect -> rotate.
        if neighbour_position == next_cell:
            return { "action": "rotate", "rotation": cells[current_cell].neighbours[neighbour_position] }

    print("current_cell:", current_cell)
    print("next_cell:", next_cell)

    # Find common ancestor in order to eventually find the path to next cell.
    # Need to go backwards to get to common ancestor. Could search for a better path towards next cell here 
    # (like using an 'inner' a* to find cheapest route from current cell to next cell).
    common_ancestor = findCommonAncestor( cells[current_cell], cells[next_cell] )
    print("common_ancestor", common_ancestor.x, common_ancestor.y)
    if (common_ancestor.x, common_ancestor.y) != current_cell:
        print("tänne mennään?")
        print("cells[current_cell].previous_cell:", cells[current_cell].previous_cell)
        print("current cell: naapurit", cells[current_cell].neighbours)
        print("xDD", cells[current_cell].neighbours[cells[current_cell].previous_cell] )
        previous_cell_rotation = cells[current_cell].neighbours[cells[current_cell].previous_cell]
        print("previous_cell_rotation:", previous_cell_rotation)

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
def traverse_path(position, rotation, path):
    print("traverse_path(): path:", path)
    if len(path) < 2:
        print("traverse_path(): Path too short")
        return None
    current_cell = path[0]
    target = path[1]
    print("traverse_path(): current_cell:", current_cell, "target:", target)
    if current_cell != position:
        print(f'traverse_path(): Unexpected position: current_cell<{current_cell}> != position<{position}>')
        return None
    
    rotation_to_next = cells[current_cell].neighbours.get(target) 
    if rotation_to_next is None:
        rotation_to_next = lib.utils.calculate_rotation_from_position(current_cell, target)
    
    if rotation != rotation_to_next:
        return { "action": "rotate", "rotation": rotation_to_next }
    else:
        path.pop(0)
        return { "action": "move" }

# Create basic cell data for the neighbours of the current cell.
def create_neighbour_cells(neighbours, position, target={'x': 999999, 'y': 999999}):
    for pos, rotation in neighbours.items():
        print("create_neighbour_cells: neighbour_pos", pos)
        if not pos in cells:
            # First time we see this cell. Initialize.
            estimate_to_target = lib.utils.calculateDistance( pos, target )
            new_cell = Cell( pos[0], pos[1], estimate_to_target )
            new_cell.set_previous_cell( position )
            cells[pos] = new_cell
            costs[pos] = costs[position] + 1
            estimates[pos] = estimate_to_target
            prio_queue.put( (distance_cost_factor*costs[pos] + estimate_to_target, pos) )
        cells[pos].neighbours[position] = lib.utils.get_opposite_angle(rotation)


# Finds common ancestor of two cells. Probably not the most efficient way to do this.
def findCommonAncestor(a, b):
    a_ancestors = []
    print("ankeuttaja:", a.x, a.y, b.x, b.y, a.previous_cell, b.previous_cell)
    if a.previous_cell is None:
        return a
    
    while a.previous_cell is not None:
        # print("a:", a.x, a.y, a.previous_cell)
        a_ancestors.append( (a.x, a.y) )
        a = cells[a.previous_cell]
    a_ancestors.append( (a.x, a.y) )  # Root cell has no previous cell, so add it manually.
    # print(a_ancestors)
    while b.previous_cell is not None:
        # print("b", b.x, b.y, b.previous_cell)
        if (b.x, b.y) in a_ancestors:
            return cells[(b.x, b.y)]
        b = cells[b.previous_cell]
    # If we got here, root cell is the common ancestor.
    return cells[(b.x, b.y)] 
 
def dfs(position, target, rotation, square):
    global shortest_path_found
    # Get neighbours for a cell if this is the first time visiting it.
    if len(cells[position].neighbours.keys()) <= 1:
        walls = lib.utils.getWalls( square )
        neighbours = lib.utils.getNeighbours(position, target, walls)
        cells[position].set_neighbours( neighbours )
        create_neighbour_cells( neighbours, position )
        stack.extend( neighbours.keys() )
    print("stack:", stack)
    # If the next cell in stack has more than one neighbour, that means we have already visited that cell and can skip it.
    # We can visit dead end cells multiple times but shouldn't be a big problem.
    current_cell = cells[position]
    next_cell = stack.pop()
    while len(cells[next_cell].neighbours.keys()) > 1:
        next_cell = stack.pop()
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
            print("TARGET FOUND")
            return { "action": "reset" }

        # Next cell was found in neighbours and the rotation is correct -> move.
        if neighbour_position == next_cell and rotation == current_cell.neighbours[neighbour_position]:
            return { "action": "move" }

        # Next cell was found in neighbours but the rotation is incorrect -> rotate.
        if neighbour_position == next_cell:
            stack.append( next_cell )  # Add the cell back to the stack.
            return { "action": "rotate", "rotation": current_cell.neighbours[neighbour_position] }

    # Next cell was not found in neighbours -> we might need to go backwards.
    # Add the cell back to the stack for now.
    stack.append( next_cell )

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


def main():
    config = dotenv_values()
    res = requests.post(
        f"https://{BACKEND_BASE}/api/levels/{config['LEVEL_ID']}",
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