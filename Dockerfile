FROM ubuntu:20.04
RUN mkdir -p /app
WORKDIR /app
COPY . /app

# Python 3.8 and pip3
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa -y
RUN apt-get install -y python3.8
RUN apt-get install -y python3-pip
RUN apt-get install -y screen
RUN apt-get install -y nano

#install google chrome
RUN apt-get install -y wget
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb

#Python requirements
RUN pip install -r requirements.txt

EXPOSE 8080