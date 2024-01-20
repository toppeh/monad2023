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
dist_traveled_factor = 0.2
dist_to_go_factor = 1
use_DFS = False

use_heuristics_in_dfs = True

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
        estimates[position] = dist_to_go_factor * lib.utils.chebyshevDistance( position, target )

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
            print("OPTIMIZING PATH DONE") #, path)

        # Travel the path to target cell.
        action = traverse_path(position, rotation, path)
    else:
        # Search for the target.
        if use_DFS:
            action = dfs(position, target, rotation, square)
        else:
            action = a_star(position, target, rotation, square)
    print("action:", action)
    return action

# Implements the A* algorithm.
def a_star(position, target, rotation, square):
    global shortest_path_found
    global costs
    current_cell = position
    
    # Get next cell. Ignore cells that to which we have already discovered the shortest path.
    next_cell = prio_queue.get()
    while next_cell[0] > costs[next_cell[1]] + estimates[next_cell[1]]:
        next_cell = prio_queue.get()  # TODO: Make exception safe.

    # We need to check if we are on the right cell to continue with algorithm.
    if current_cell == next_cell[1]:
         # We are on the cell with the most potential, so we can proceed with the algorithm.

        # Try to straighten the corner leading to this cell, if there is one. Hopefully this will ease traveling back and forth.
        if cells[current_cell].previous_cell is not None:
            print("attempting to optimize corner")
            parent = cells[current_cell].previous_cell
            if cells[parent].previous_cell is not None:
                grandparent = cells[parent].previous_cell
                print("current_cell:", current_cell, "parent:", parent, "grandparent:", grandparent)
                costs = lib.utils.optimize_corner(current_cell, grandparent, cells, costs)


        # Initialize the neighbours if this is the first time visiting this cell.
        if not cells[position].visited:
            walls = lib.utils.getWalls( square )
            neighbours = lib.utils.getNeighbours(position, walls)
            cells[position].set_neighbours( neighbours )
            create_neighbour_cells( neighbours, position, costs, target )
            cells[position].set_visited()
        
        # Update estimates for neighbours.
        for neighbour_position, neighbour_rotation in cells[current_cell].neighbours.items():
            # Target found, stop algorithm.
            if neighbour_position == (target['x'], target['y']):
                print("SHORTEST PATH FOUND")
                shortest_path_found = True
                target_cell = Cell( target['x'], target['y'] )
                target_cell.set_previous_cell( position )
                cells[(target['x'], target['y'])] = target_cell
                return { "action": "reset" }

            # Check cost from current cell to neighbour.
            cost_from_current = costs[current_cell] + 1
            if cost_from_current < costs[neighbour_position]:
                # Found a shorter path to this neighbour, update cell data.
                costs[neighbour_position] = cost_from_current
                prio_queue.put( (dist_traveled_factor * cost_from_current + estimates[neighbour_position], neighbour_position) )
                cells[neighbour_position].set_previous_cell( current_cell )
    
    # We are not on the right cell for the algorithm, so put the cell back in the queue for now.
    else:
        prio_queue.put( next_cell )
    
    # We need to move to the next cell in prio queue to proceed with algorithm.
    next_cell = prio_queue.queue[0][1]

    # Before searching for common ancestor between current cell and next cell check for next cell in current cell's neighbours.
    # This might save time as next cell is somewhat likely to be a neighbour.
    for neighbour_position, neighbour_rotation in cells[current_cell].neighbours.items():
        if neighbour_position == next_cell and rotation == neighbour_rotation:
            return { "action": "move" }
        # Next cell was found in neighbours but the rotation is incorrect -> rotate.
        if neighbour_position == next_cell:
            return { "action": "rotate", "rotation": cells[current_cell].neighbours[neighbour_position] }

    # Find common ancestor in order to eventually find the path to next cell.
    # Need to go backwards to get to common ancestor. Could search for a better path towards next cell here 
    # (like using an 'inner' a* to find cheapest route from current cell to next cell).
    common_ancestor = findCommonAncestor( cells[current_cell], cells[next_cell] )

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
def traverse_path(position, rotation, path):
    if len(path) < 2:
        print("traverse_path(): Path too short")
        return None
    current_cell = path[0]
    target = path[1]
    print("traverse_path(): current_cell:", current_cell, "len(path):", len(path))
    if current_cell != position:
        print(f'traverse_path(): Unexpected position: current_cell<{current_cell}> != position<{position}>')
        return None
    
    rotation_to_next = cells[current_cell].neighbours.get(target) 
    if rotation_to_next is None:
        rotation_to_next = dist_to_go_factor * lib.utils.calculate_rotation_from_position(current_cell, target)
    
    if rotation != rotation_to_next:
        return { "action": "rotate", "rotation": rotation_to_next }
    else:
        path.pop(0)
        return { "action": "move" }

# Create basic cell data for the neighbours of the current cell.
def create_neighbour_cells(neighbours, position, costs={}, target={'x': 999999, 'y': 999999}):
    for pos, rotation in neighbours.items():
        if not pos in cells:
            # First time we see this cell. Initialize.
            estimate_to_target = dist_to_go_factor * lib.utils.chebyshevDistance( pos, target )
            new_cell = Cell( pos[0], pos[1], estimate_to_target )
            new_cell.set_previous_cell( position )
            cells[pos] = new_cell
            costs[pos] = costs[position] + 1
            estimates[pos] = estimate_to_target
            prio_queue.put( (dist_traveled_factor*costs[pos] + estimate_to_target, pos) )
        
        # Detect loops.
        if use_DFS and cells[pos].previous_cell != position and pos != cells[position].previous_cell:
            # Loop detected. This neighbour will have a shorter path to the start cell so go back in the path
            # and update previous cell data.
            print("pls no")
            costs = lib.utils.update_cell_previous_path( position, pos, cells, costs )

        cells[pos].neighbours[position] = lib.utils.get_opposite_angle(rotation)


# Finds common ancestor of two cells. Not the most efficient way to do this.
# Collects all ancestors of a and then searches for the first common ancestor with b.
def findCommonAncestor(a, b):
    a_ancestors = []
    if a.previous_cell is None:
        return a
    
    # Collect all ancestors of a.
    while a.previous_cell is not None:
        a_ancestors.append( (a.x, a.y) )
        a = cells[a.previous_cell]
    a_ancestors.append( (a.x, a.y) )  # Root cell has no previous cell, so add it manually.

    # Go through b's ancestor's
    while b.previous_cell is not None:
        if (b.x, b.y) in a_ancestors:
            # Common ancestor found.
            return cells[(b.x, b.y)]
        b = cells[b.previous_cell]

    # If we got here, root cell is the common ancestor.
    return cells[(b.x, b.y)] 
 
def dfs(position, target, rotation, square):
    global shortest_path_found
    # Get neighbours for a cell if this is the first time visiting it.
    if not cells[position].visited:
        walls = lib.utils.getWalls( square )
        neighbours = lib.utils.getNeighbours(position, walls)
        cells[position].set_neighbours( neighbours )
        create_neighbour_cells( neighbours, position, costs )

        # Add neighbours to stack in order of distance to target.
        # This heuristic was implemented because of the increasing maze size. Not sure if actually helpful.
        if use_heuristics_in_dfs:
            neighbours_by_dist = list()
            for neighbour in neighbours.keys():
                neighbours_by_dist.append( ( dist_to_go_factor * lib.utils.calculateDistance( neighbour, target ), neighbour) )
            sort_by_dist = lambda x: x[0]
            neighbours_by_dist.sort(reverse=True, key=sort_by_dist)
            for i in neighbours_by_dist:
                stack.append( i[1] )
        else:
            # Just add neighbours to stack in 'random' order.
            stack.extend( neighbours.keys() )
        cells[position].set_visited()

    # Choose next_cell but skip visited cells.
    current_cell = cells[position]
    next_cell = stack.pop()
    while cells[next_cell].visited or next_cell == (current_cell.x, current_cell.y):  # second condition is needed. Source: trust me.
        next_cell = stack.pop()
    # print("next_cell:", next_cell)
    print("len(saved_cells):", len(cells))
    print("len(stack):", len(stack))
    print("next_cell:", next_cell)

    # Search current cell's neighbours for the next cell.
    for neighbour_position, neighbour_rotation in current_cell.neighbours.items():
        # print("neighbour: ", neighbour_position, neighbour_rotation)
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

    # Need to go backwards to get to common ancestor.
    if common_ancestor != current_cell:
        previous_cell_rotation = current_cell.neighbours[current_cell.previous_cell]
        if rotation == previous_cell_rotation:
            return { "action": "move" }
        else:
            return { "action": "rotate", "rotation": previous_cell_rotation }

    # Current cell is the common ancestor, so we can traverse the path to the next cell.
    else:
        # Navigate to the cell that will take us towards the next cell.
        while cells[next_cell].previous_cell != (current_cell.x, current_cell.y):
            next_cell = cells[next_cell].previous_cell
        new_target_rotation = current_cell.neighbours[next_cell]
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