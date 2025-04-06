from flask import Flask, render_template, request, redirect, url_for
import subprocess
import threading

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_views', methods=['POST'])
def generate_views():
    website = request.form['website']
    max_clicks = request.form['max_clicks']

    # Start the traffic generation process in a separate thread
    threading.Thread(target=generate_traffic, args=(website, max_clicks), daemon=True).start()

    return render_template('loading.html')

def generate_traffic(website, max_clicks):
    threads = 10
    min_clicks = 2
    timeout = 60
    max_offset = 10

    # Construct the command with the provided inputs
    command = f"python main.py -d {website} --forever --threads {threads} --max-clicks {max_clicks} --min-clicks {min_clicks} --forever --timeout {timeout} --max-offset {max_offset}"

    # Execute the command
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        text=True
    )

    # Read and display the output in the terminal
    while process.poll() is None:
        line = process.stdout.readline()
        print(line)  # Output to the Flask console

    # After the traffic generation is complete, redirect to the success page
    return redirect(url_for('success'))

@app.route('/success')
def success():
    return 'Another chrome window will pop up, please do not close it unless you did not input the correct domain!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)