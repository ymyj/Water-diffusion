from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from simulation import SoilPollutionSimulator
import threading
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_for_demo'
socketio = SocketIO(app, cors_allowed_origins="*")

simulator = None
simulation_thread = None
is_running = False


@app.route('/')
def index():
    with open(os.path.join(os.path.dirname(__file__), 'templates', 'index.html'), 'r', encoding='utf-8') as f:
        return f.read()


@app.route('/api/simulate', methods=['POST'])
def start_simulation():
    global simulator, simulation_thread, is_running
    
    if is_running:
        return jsonify({'error': 'Simulation already running'}), 400
    
    params = request.json
    simulator = SoilPollutionSimulator(params)
    
    is_running = True
    simulation_thread = threading.Thread(target=run_simulation)
    simulation_thread.daemon = True
    simulation_thread.start()
    
    return jsonify({'status': 'started'})


@app.route('/api/stop', methods=['POST'])
def stop_simulation():
    global is_running
    is_running = False
    return jsonify({'status': 'stopped'})


@app.route('/api/reset', methods=['POST'])
def reset_simulation():
    global simulator, is_running
    is_running = False
    if simulator:
        simulator.reset()
        # 渲染初始帧
        initial_frame = simulator.render_frame(simulator.c, 0)
        socketio.emit('frame', {'image': initial_frame, 'step': 0, 'time': 0})
    return jsonify({'status': 'reset'})


@app.route('/api/params', methods=['GET'])
def get_default_params():
    temp_sim = SoilPollutionSimulator()
    return jsonify(temp_sim.default_params)


def run_simulation():
    global is_running, simulator
    
    if not simulator:
        return
    
    steps = simulator.steps
    frame_interval = 25  # 每25步发送一帧
    
    for step in range(steps):
        if not is_running:
            break
        
        simulator.c = simulator.solve_step(simulator.c, step)
        
        if step % frame_interval == 0:
            frame_image = simulator.render_frame(simulator.c, step)
            time_days = step * simulator.dt
            socketio.emit('frame', {
                'image': frame_image,
                'step': step,
                'time': time_days,
                'total_steps': steps
            })
    
    socketio.emit('simulation_complete')
    is_running = False


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8000)