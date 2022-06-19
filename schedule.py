from bs4 import BeautifulSoup
from httpx import AsyncClient
import glob, sys, fitz
import PIL
from math import sqrt
from PIL import Image
import os
import asyncio


async def download_schedule_pdf():
    try:
        async with AsyncClient() as client:
            r = await client.get('http://famicon.adygnet.ru/')
            soup = BeautifulSoup(r.text, 'html.parser')

            # ищем блок Новости и События, там хранятся ссылки на расписание
            schedule_block = soup.find('aside', class_='widget inner-padding widget_recent_entries')
            records = schedule_block.find('ul').find_all('a')
            current_schedule_ref = None

            schedule_refs = []

            # среди всех записей находим те, которые содержат слово "неделя" и "красная"/"черная"
            # первая попавшаяся запись - самая новая и нужная
            for r in records:
                text = str(r.text).lower()
                if text.find('неделя') and (text.find('красная') or text.find('черная') or text.find('черная')):
                    schedule_refs.append(r.attrs['href'])
                if len(schedule_refs) == 2:
                    break

            schedule_refs = {
                'newest': schedule_refs[0],
                'old': schedule_refs[-1]
            }
            res = {
                'newest': [],
                'old': []
            }
            for kind, current_schedule_ref in schedule_refs.items():
                # переходим по ссылке, чтобы скачать файл
                r = await client.get(current_schedule_ref)
                soup = BeautifulSoup(r.text, 'html.parser')

                # находим кнопку скачать и получаем из нее ссылку на скачивание
                download_link: str = soup.find('p', class_='embed_download').contents[0].attrs['href']

                # переходим по ссылке и получаем pdf файл с расписанием
                schedule_file = await client.get(download_link)

                # генерируем имя файла
                file_name = download_link[download_link.rfind('/') + 1:]

                directory = f'schedules/{kind}'
                # сохраняем pdf файл в папку schedules
                with open(f'{directory}/{file_name}', 'wb') as f:
                    f.write(schedule_file.content)
                png_files = convert_to_png(directory)
                crop_files = crop_main_fragment(png_files)
                splitted = get_schedule_for_course_from_cropped(crop_files)
                res[kind] = splitted
                remove_old_version(directory, file_name[:-4])
    except Exception as e:
        print('Не удалось подключиться к фамикону.', e)
    return res


def convert_to_png(path):
    # копипаст из интернета для преобразования pdf в png
    zoom_x = 4.0  # horizontal zoom
    zoom_y = 4.0  # vertical zoom
    mat = fitz.Matrix(zoom_x, zoom_y)  # zoom factor 2 in each dimension

    directory = f'{path}/'
    all_files = glob.glob(directory + "*.pdf")

    res = []
    for filename in all_files:
        doc = fitz.open(filename)  # open document
        for page in doc:  # iterate through the pages
            pix = page.get_pixmap(matrix=mat)  # render page to an image
            png_name = filename[filename.rfind('\\') + 1:][:-4]
            png_name = f"{directory}{png_name}.png"
            res.append(png_name)
            pix.save(png_name)  # store image as a PNG
    return res


def color_dist(a, b):
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


# вырезаем только расписание
def crop_main_fragment(png_files):
    crop_res = []
    for image_name in png_files:
        im = Image.open(image_name)
        width, height = im.size

        white_x = 0
        while im.getpixel((white_x, height / 2)) == (255, 255, 255):
            white_x += 1
        white_x = max(0, white_x - 2)
        for x in range(white_x, white_x + 7):
            for y in range(height):
                if color_dist(im.getpixel((x, y)), (255, 255, 255)) < 200 and im.getpixel((x+3, y)) == (255, 255, 255):
                    im.putpixel((x, y), (255, 255, 255))
        # Process every pixel
        x = 0
        y = height / 2
        while im.getpixel((x, y)) == (255, 255, 255):
            x += 1
        line_reach = (x, y)
        while im.getpixel((x, y)) != (255, 255, 255):
            y -= 1
        left_top_corner = (int(x), int(y + 1))

        for x in range(width):
            for y in range(left_top_corner[1] - 3, left_top_corner[1] + 4):
                if color_dist(im.getpixel((x, y)), (255, 255, 255)) < 200 and im.getpixel((x, y+3)) == (255, 255, 255):
                    im.putpixel((x, y), (255, 255, 255))
        x, y = line_reach
        while im.getpixel((x, y)) != (255, 255, 255):
            y += 1
        y -= 1

        while im.getpixel((x, y)) != (255, 255, 255):
            x += 1

        right_bot_corner = (x - 1, y)
        box = (*left_top_corner, *right_bot_corner)
        cropped = im.crop(box)
        #
        # width, height = cropped.size
        # # заменим серый цвет, который почти белый, на белый
        # for x in range(width):
        #     for y in range(height):
        #         if color_dist(cropped.getpixel((x, y)), (255, 255, 255)) < 96:
        #             cropped.putpixel((x, y), (255, 255, 255))
        cropped_name = im.filename[:-4] + '_cropped.png'
        cropped.save(cropped_name)
        crop_res.append(cropped_name)
    return crop_res


def get_schedule_for_course_from_cropped(cropped_files):
    res = []
    for image_name in cropped_files:
        im = Image.open(image_name)
        width, height = im.size
        schedule_box = [0, 0, 0, height]
        x, y = 5, 5

        line_reach = 0
        last_pixel_line = False
        while line_reach != 2:
            if not last_pixel_line:
                line_reach += im.getpixel((x, y)) != (255, 255, 255)
            last_pixel_line = im.getpixel((x, y)) != (255, 255, 255)
            x += 1

        line_reach_vertical = {
            0: None,  # группы
            1: 0,  # понедельник
            2: 0,  # вторник
            3: 0,  # среда
            4: 0,  # четверг
            5: 0,  # пятница
            6: 0,  # суббота
            7: 0   # воскресенье
        }

        loc_x = x - 4
        loc_y = y - 2
        while im.getpixel((loc_x, loc_y)) == (255, 255, 255):
            loc_y += 1
        line_reach_vertical[0] = loc_y
        loc_y += 2
        loc_x = 3
        while im.getpixel((loc_x, loc_y)) == (255, 255, 255):
            loc_x += 1
        day = 0

        def white_line():
            return (
                    im.getpixel((loc_x, loc_y)) == (255, 255, 255)
                and im.getpixel((loc_x - 1, loc_y)) == (255, 255, 255)
                and im.getpixel((loc_x - 2, loc_y)) == (255, 255, 255)
                and im.getpixel((loc_x + 1, loc_y)) == (255, 255, 255)
                and im.getpixel((loc_x + 2, loc_y)) == (255, 255, 255)
            )
        while loc_x < im.size[0] and loc_y < im.size[1]:
            day += 1
            line_reach = 0
            last_pixel_line = False
            while loc_y < im.size[1] and not (white_line()):
                loc_y += 1
            line_reach_vertical[day] = loc_y - 1

            while loc_y < im.size[1] and im.getpixel((loc_x, loc_y)) == (255, 255, 255):
                loc_y += 1


        # получили границы расписания времени занятий
        schedule_box[2] = x
        schedule_box = tuple(schedule_box)
        schedule = im.crop(schedule_box)

        course_box = {
            1: [schedule_box[2], 0, 0, height],
            2: [0, 0, 0, height],
            3: [0, 0, 0, height],
            4: [0, 0, width, height]
        }

        y = 5
        loc_x = x + 4

        while im.getpixel((loc_x, y)) == (255, 255, 255):
            y -= 1
        y += 2

        for i in range(1, 4):
            x += 1
            course_box[i][0] = x - 1
            while im.getpixel((x, y)) == (255, 255, 255):
                x += 1

            while im.getpixel((x, y)) != (255, 255, 255):
                x += 1

            course_box[i][2] = x - 1
            x += 1
            while x < im.size[0] and y < im.size[1] and im.getpixel((x, y)) == (255, 255, 255):
                x += 1

            while x < im.size[0] and y < im.size[1] and im.getpixel((x, y)) != (255, 255, 255):
                x += 1

        course_box[4][0] = x
        for course, box in course_box.items():
            if box[2] - box[0] < 600:
                continue
            course_schedule = Image.new("RGB", (schedule_box[2] + box[2] - box[0], height), "white")
            course_schedule.paste(schedule, (0, 0))
            course_crop = im.crop(box)
            course_schedule.paste(course_crop, (schedule_box[2], 0))
            main_file_name = im.filename[:im.filename.find('crop')]

            # нарезка по дням
            day_name = {
                1: 'понедельник',
                2: 'вторник',
                3: 'среда',
                4: 'четверг',
                5: 'пятница',
                6: 'суббота',
                7: 'воскресенье',
            }
            for i in range(1, 8):

                if line_reach_vertical[i] == 0:
                    break
                top_fragment = course_schedule.crop((0, 0, course_schedule.size[0] - 1, line_reach_vertical[0]))
                for x in range(top_fragment.size[0]):
                    top_fragment.putpixel((x, top_fragment.size[1] - 1), (0, 0, 0))

                start_y = line_reach_vertical[i - 1]
                end_y = line_reach_vertical[i]
                main_fragment = course_schedule.crop((0, start_y, course_schedule.size[0] - 1, end_y))
                day_schedule = Image.new(
                    "RGB",
                    (course_schedule.size[0], top_fragment.size[1] + main_fragment.size[1]),
                    "white"
                )
                day_schedule.paste(top_fragment, (0, 0))
                day_schedule.paste(main_fragment, (0, top_fragment.size[1]))
                day_filename = main_file_name + f'{course}_курс_{day_name[i]}.png'
                day_schedule.save(day_filename)
            course_filename = main_file_name + f'{course}_курс.png'
            course_schedule.save(course_filename)
            res.append(course_filename)
    return res


def remove_old_version(path, template=None):
    for filename in os.listdir(path):
        file_path = os.path.join(path, filename)
        if filename.find(template) != -1:
            continue
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f'Не удалось удалить {file_path}. Причина: {e}')