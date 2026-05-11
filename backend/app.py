from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from simulation import SoilPollutionSimulator
import threading
import os
import io
import base64
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_key_for_demo'
socketio = SocketIO(app, cors_allowed_origins="*")

simulator = None
simulation_thread = None
is_running = False
frames_store = []


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
    global simulator, is_running, frames_store
    is_running = False
    frames_store = []
    if simulator:
        simulator.reset()
        # 渲染初始帧
        initial_frame = simulator.render_frame(simulator.c, 0)
        stats = simulator.calculate_stats()
        depth_data, concentration_data = simulator.get_depth_profile()
        socketio.emit('frame', {
            'image': initial_frame,
            'step': 0,
            'time': 0,
            'total_steps': simulator.steps,
            'stats': stats,
            'depth_data': depth_data,
            'concentration_data': concentration_data
        })
    return jsonify({'status': 'reset'})


@app.route('/api/export-animation', methods=['GET'])
def export_animation():
    global frames_store
    if not frames_store:
        return jsonify({'error': 'No frames to export'}), 400
    
    try:
        images = []
        for frame_data in frames_store:
            img_data = base64.b64decode(frame_data)
            img = Image.open(io.BytesIO(img_data))
            img = img.convert('RGB')
            images.append(img)
        
        output = io.BytesIO()
        images[0].save(
            output,
            format='GIF',
            append_images=images[1:],
            save_all=True,
            duration=80,
            loop=0,
            optimize=False
        )
        output.seek(0)
        return send_file(output, mimetype='image/gif', as_attachment=True, download_name='simulation.gif')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/params', methods=['GET'])
def get_default_params():
    temp_sim = SoilPollutionSimulator()
    return jsonify(temp_sim.default_params)


@socketio.on('connect')
def handle_connect():
    if simulator:
        initial_frame = simulator.render_frame(simulator.c, 0)
        stats = simulator.calculate_stats()
        depth_data, concentration_data = simulator.get_depth_profile()
        emit('frame', {
            'image': initial_frame,
            'step': 0,
            'time': 0,
            'total_steps': simulator.steps,
            'stats': stats,
            'depth_data': depth_data,
            'concentration_data': concentration_data
        })


def run_simulation():
    global is_running, simulator, frames_store
    
    if not simulator:
        return
    
    frames_store = []
    steps = simulator.steps
    frame_interval = 25  # 每25步发送一帧
    
    for step in range(steps):
        if not is_running:
            break
        
        simulator.c = simulator.solve_step(simulator.c, step)
        
        if step % frame_interval == 0:
            frame_image = simulator.render_frame(simulator.c, step)
            time_days = step * simulator.dt
            stats = simulator.calculate_stats()
            depth_data, concentration_data = simulator.get_depth_profile()
            
            # 存储帧用于导出
            frames_store.append(frame_image)
            
            socketio.emit('frame', {
                'image': frame_image,
                'step': step,
                'time': time_days,
                'total_steps': steps,
                'stats': stats,
                'depth_data': depth_data,
                'concentration_data': concentration_data
            })
    
    socketio.emit('simulation_complete')
    is_running = False


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=8000)