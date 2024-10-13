from flask import Flask, request, render_template, session, redirect, abort, flash

app = Flask("SkysmartMakerService")

app.secret_key = 'AUfy1@#uig!!jf?5r&^@!'


@app.get('/setauth')
def setauth():
    return render_template("setauth.html")


@app.post('/setauth')
def setauthpost():
    from maker import SkysmartMaker, MessageException

    resp = redirect('/')

    try:
        SkysmartMaker('test').auth(request.form['email'], request.form['password'])
    except MessageException:
        flash("Неправильный логин или пароль")
    except Exception:
        flash("Произошла непредвиденная ошибка на стороне сервера")
    else:
        for key in ('email', 'password'):
            resp.set_cookie(key, request.form[key], httponly=True)

        session['authorized'] = True
        return resp

    return render_template("setauth.html")


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
    between: int = int(config['between'])

    cookies = request.cookies

    # TODO: Give client message id, not message content, move this to client
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
        from exceptions import MessageException
        error = ':'
        try:
            for state in SkysmartMaker(task, score, between).do(cookies['email'], cookies['password']):
                yield '|' + handle_state(state)  # Add separator
        except MessageException as e:
            error += e.message
        except Exception as e:
            print(e.message)
            error += 'unhandled'
        yield '|end' + error

    return start_maker(), {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    app.run(debug=True)
