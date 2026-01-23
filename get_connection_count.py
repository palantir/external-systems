import requests
import re

def get_downstream_connections(host='localhost', port=9901, listener='0.0.0.0_8080'):
    """
    Get total number of active downstream connections from Envoy.
    
    Args:
        host: Envoy admin interface host
        port: Envoy admin interface port
        listener: Listener address pattern (default: 0.0.0.0_8080)
    
    Returns:
        int: Total active downstream connections
    """
    url = f'http://{host}:{port}/stats'
    response = requests.get(url)
    response.raise_for_status()
    
    # Match lines like: listener.0.0.0.0_8080.worker_X.downstream_cx_active: 5
    pattern = rf'listener\.{re.escape(listener)}\.worker_\d+\.downstream_cx_active:\s*(\d+)'
    
    total = 0
    for match in re.finditer(pattern, response.text):
        total += int(match.group(1))
    
    return total

# Usage
if __name__ == '__main__':
    connections = get_downstream_connections()
    print(f"Total active downstream connections: {connections}")