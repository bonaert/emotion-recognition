from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
import uvicorn, aiohttp, asyncio
from io import BytesIO
import base64

from fastai import *
from fastai.vision import *

# Setup app
app = Starlette()
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_headers=['X-Requested-With', 'Content-Type'])
app.mount('/static', StaticFiles(directory='app/static'))



# Setup model
model_file_url = 'https://www.dropbox.com/s/jjdot7spdg7e7du/stage-2-emotionsSimple.pth?raw=1'
model_file_name = 'model'
classes = ['happy', 'sad', 'angry', 'surprised', 'disgusted']

path = Path(__file__).parent
async def download_file(url, dest):
    if dest.exists(): return
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.read()
            with open(dest, 'wb') as f: f.write(data)

async def setup_learner():
    await download_file(model_file_url, path/'models'/f'{model_file_name}.pth')
    data_bunch = ImageDataBunch.single_from_classes(path, classes,
        ds_tfms=get_transforms(), size=224).normalize(imagenet_stats)
    learn = create_cnn(data_bunch, models.resnet50, pretrained=False)
    learn.load(model_file_name)
    return learn

loop = asyncio.get_event_loop()
tasks = [asyncio.ensure_future(setup_learner())]
learn = loop.run_until_complete(asyncio.gather(*tasks))[0]
loop.close()



# Routes

# Main page: return index
@app.route('/')
def index(request):
    html = path/'view'/'index.html'
    return HTMLResponse(html.open().read())

# Classification route: receive an image, predict an emotion
@app.route('/classify', methods=['POST'])
async def classify(request):
    data = await request.form()
    img_bytes = await (data['imgBase64'].read())
    decoded_img_bytes = base64.decode(img_bytes)
    img = open_image(BytesIO(decoded_img_bytes))
    
    pred_class, pred_index, losses = learn.predict(img)
    result = sorted(
        zip(map(str, learn.data.classes), map(float, losses)),
        key= lambda p: p[1],
        reverse=True
    )


    return JSONResponse({'predictions': result})

if __name__ == '__main__':
    if 'serve' in sys.argv: uvicorn.run(app, host='0.0.0.0', port=8080)

