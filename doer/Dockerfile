# pull official base image
FROM python:3.9.6-alpine

# set work directory
WORKDIR /usr/src/app

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev
RUN pip install -r requirements.txt

# copy project
COPY . .

CMD [ "python", "./main.py" ]