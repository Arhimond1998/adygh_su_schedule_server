import datetime
from fastapi import FastAPI, HTTPException, Depends
from http import HTTPStatus
from fastapi_utils.tasks import repeat_every
from fastapi.responses import FileResponse
import uvicorn
import asyncio
import os
from schedule import download_schedule_pdf


app = FastAPI()


def get_file_path_course(directory, course):
    for filename in os.listdir(directory):
        if filename.find(f'{course}_курс.png') != -1:
            file_path = os.path.join(directory, filename)
            return file_path
    raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Расписание не найдено")


def get_path_full_schedule(directory):
    for filename in os.listdir(directory):
        if filename.find('.pdf') != -1:
            file_path = os.path.join(directory, filename[:-4] + '.png')
            return file_path


@app.get('/get_course_schedule_newest/{course}')
async def get_course_schedule_newest(course: int):
    directory = 'schedules/newest'
    file_path = get_file_path_course(directory, course)
    return FileResponse(file_path, media_type="image/png")


@app.get('/get_course_schedule_old/{course}')
async def get_course_schedule_old(course: int):
    directory = 'schedules/old'
    file_path = get_file_path_course(directory, course)
    return FileResponse(file_path, media_type="image/png")


@app.get('/get_schedule_pdf_info')
async def get_schedule_pdf_info():
    directories = ['schedules/newest', 'schedules/old']
    res = []
    for directory in directories:
        for filename in os.listdir(directory):
            if filename.find('.pdf') != -1:
                res.append(filename)
    return res

@app.get('/get_today_schedule/{course}')
async def get_today_schedule(course: int):
    directories = ['schedules/newest', 'schedules/old']
    day, month = map(int, datetime.datetime.now().strftime('%d %m').split())
    res = []
    months = {
        'январ': 1,
        'феврал': 2,
        'март': 3,
        'апрел': 4,
        'май': 5,
        'мая': 5,
        'июн': 6,
        'июл': 7,
        'август': 8,
        'сентябр': 9,
        'октябр': 10,
        'ноябр': 11,
        'декабр': 12
    }
    day_names = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
    for directory in directories:
        for filename in os.listdir(directory):
            if filename.find('.pdf') != -1:
                res.append((directory, filename))

    for directory, pdf_name in res:
        file_month = month
        for month_name, month_num in months.items():
            if pdf_name.find(month_name) != -1:
                file_month = month_num
                break
        if file_month == month:
            pdf_name_splitted = pdf_name.replace('-', ' ').replace('(', ' ').replace(')', ' ').split()
            numbers = list(map(int, [x for x in pdf_name_splitted if x.isdigit()]))
            week_day = numbers[0]
            week = dict()
            for day_name in day_names:
                week[week_day] = day_name
                week_day += 1

            for filename in os.listdir(directory):
                if filename.find(f'{course}_курс_{week.get(day, "абракадабра")}.png') != -1:
                    file_path = os.path.join(directory, filename)
                    return FileResponse(file_path, media_type="image/png")
    raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Расписание на сегодня не найдено")


@app.get('/get_full_schedule_newest')
async def get_full_schedule_newest():
    directory = 'schedules/newest'
    file_path = get_path_full_schedule(directory)
    return FileResponse(file_path, media_type="image/png")


@app.get('/get_full_schedule_old')
async def get_full_schedule_old():
    directory = 'schedules/old'
    file_path = get_path_full_schedule(directory)
    return FileResponse(file_path, media_type="image/png")


@app.on_event("startup")
@repeat_every(seconds=60 * 60)  # 1 hour
async def download_schedules() -> None:
    await download_schedule_pdf()
    print('Обновили ПДФ')


if __name__ == '__main__':
    uvicorn.run('main:app', host='localhost', port=8000, reload=True, workers=8)