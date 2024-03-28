from flask import Flask, request, render_template, session, redirect

app = Flask("SkysmartMakerService")

app.secret_key = 'AUfy1@#uig!!jf?5r&^@!'


@app.get('/setauth')
def setauth():
    return render_template("setauth.html")


@app.post('/setauth')
def setauthpost():
    resp = redirect('/')
    for key, value in request.form.items():
        resp.set_cookie(key, value, httponly=True)
    session['authorized'] = True
    return resp


@app.get('/')
def index():
    if not session.get('authorized'):
        return redirect('/setauth')
    return render_template('index.html')


@app.post('/maker')
def maker():
    from maker import SkysmartMaker, StateEnum

    config = request.json
    task = config['url'].split('/')[-1]
    score: int = int(config['score'])

    cookies = request.cookies

    messages = {
        StateEnum.AUTH: "Авторизация...",
        StateEnum.START: "Запуск задания...",
        StateEnum.SETUP: "Подготовка...",
        StateEnum.DO: "{} из {} задач",
        StateEnum.FINISH: "Завершено!",
    }

    def handle_state(state) -> str:
        state_enum: StateEnum = state['state']
        state_data = state.get('data')

        msg = messages[state_enum]
        if state_data is not None:
            msg = msg.format(*state_data)
        return msg

    def start_maker():
        for state in SkysmartMaker(task, score).do(cookies['email'], cookies['password']):
            yield handle_state(state)

    return start_maker(), {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    app.run(debug=True)
