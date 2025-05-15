
Using cached tzlocal-5.3.1-py3-none-any.whl (18 kB)
Using cached uvloop-0.21.0-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (4.0 MB)
Using cached watchfiles-1.0.5-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (454 kB)
Using cached websockets-15.0.1-cp311-cp311-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl (182 kB)
Using cached certifi-2025.4.26-py3-none-any.whl (159 kB)
Using cached uvicorn-0.34.2-py3-none-any.whl (62 kB)
Using cached annotated_types-0.7.0-py3-none-any.whl (13 kB)
Using cached typing_inspection-0.4.0-py3-none-any.whl (14 kB)
Installing collected packages: websockets, uvloop, tzlocal, typing-extensions, sniffio, pyyaml, python-dotenv, idna, httptools, h11, click, certifi, annotated-types, uvicorn, typing-inspection, pydantic-core, httpcore, apscheduler, anyio, watchfiles, starlette, pydantic, httpx, python-telegram-bot, fastapi
Successfully installed annotated-types-0.7.0 anyio-4.9.0 apscheduler-3.11.0 certifi-2025.4.26 click-8.2.0 fastapi-0.115.12 h11-0.16.0 httpcore-1.0.9 httptools-0.6.4 httpx-0.25.2 idna-3.10 pydantic-2.11.4 pydantic-core-2.33.2 python-dotenv-1.1.0 python-telegram-bot-20.6 pyyaml-6.0.2 sniffio-1.3.1 starlette-0.46.2 typing-extensions-4.13.2 typing-inspection-0.4.0 tzlocal-5.3.1 uvicorn-0.34.2 uvloop-0.21.0 watchfiles-1.0.5 websockets-15.0.1
[notice] A new release of pip is available: 24.0 -> 25.1.1
[notice] To update, run: pip install --upgrade pip
==> Uploading build...
==> Uploaded in 9.0s. Compression took 1.0s
==> Build successful 🎉
==> Deploying...
==> Running 'python main.py'
==> No open ports detected, continuing to scan...
==> Docs on specifying a port: https://render.com/docs/web-services#port-binding
/opt/render/project/src/main.py:117: DeprecationWarning: 
        on_event is deprecated, use lifespan event handlers instead.
        Read more about it in the
        [FastAPI docs for Lifespan Events](https://fastapi.tiangolo.com/advanced/events/).
        
  @app_fastapi.on_event("startup")
INFO:     Started server process [82]
INFO:     Waiting for application startup.
INFO:apscheduler.scheduler:Scheduler started
INFO:root:🕛 Планировщик задач запущен.
INFO:httpx:HTTP Request: POST https://api.telegram.org/bot7367453134:AAFUPFACGmP528DuWEVSM_L9l2ypVnmTKoA/getMe "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: POST https://api.telegram.org/bot7367453134:AAFUPFACGmP528DuWEVSM_L9l2ypVnmTKoA/setWebhook "HTTP/1.1 200 OK"
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000 (Press CTRL+C to quit)
INFO:     127.0.0.1:58478 - "HEAD / HTTP/1.1" 405 Method Not Allowed
==> Your service is live 🎉
INFO:     35.197.118.178:0 - "GET / HTTP/1.1" 200 OK
ERROR:telegram.ext.Application:No error handlers are registered, logging exception.
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.11/site-packages/telegram/ext/_application.py", line 1195, in process_update
    await coroutine
  File "/opt/render/project/src/.venv/lib/python3.11/site-packages/telegram/ext/_basehandler.py", line 153, in handle_update
    return await self.callback(update, context)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/main.py", line 91, in handle_text
    if update.effective_chat.id != int(GROUP_ID): return
                                   ^^^^^^^^^^^^^
ValueError: invalid literal for int() with base 10: '-100xxxxxxxxxx'
INFO:     91.108.5.17:0 - "POST /webhook HTTP/1.1" 200 OK
