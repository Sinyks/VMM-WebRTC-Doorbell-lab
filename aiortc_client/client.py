import asyncio
import json
import secrets
import socketio
import logger

from telegram import bot

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay

options_video = {"framerate": "30", "video_size": "320x240"}

sio = socketio.AsyncClient(ssl_verify=False)

MAX_RND = 512

HOST = 'https://<Signaling_Server_IP>'
PORT = 443

BOT_TOKEN = "Your bot token here"
CHAT_ID = 0# Your Chat ID here

LOG = logger.get_logger()

#tg = bot.Bot(BOT_TOKEN)


# Reception des messages asynchrones
def receiver_queue(signaling, messages):
    queue = asyncio.Queue()
    for signal in messages:
        signaling.on(signal, lambda content, signal=signal: queue.put_nowait((signal, content)))
    return queue


async def main(server):
    input("Press Enter to continue...")
    pc = None
    await sio.connect(server)
    LOG.info("connected to my server")
    LOG.info("sending test message")

    room_name = "room_pi{}".format(secrets.randbelow(MAX_RND))

    queue = receiver_queue(sio, messages=["joined", "created", "full", "invite", "ice_candidate", "bye", "new_peer"])

    await sio.emit('join', room_name)

    while True:
        LOG.info("get signal from queue")
        message = await queue.get()

        LOG.debug(message)

        if message[0] == "created":
            url = f"{server}?room={message[1]}"
            LOG.info(f"room {message[1]} has been created")
            LOG.info(f"Browse your navigator to {url}")
            #tg.send_message(chat_id=CHAT_ID, text="You can see your camera here {url}")

        if message[0] in ("full", "joined"):
            LOG.info("error : room already exist")

        if message[0] == "new_peer":
            LOG.info("a new peer has entered the room")

        if message[0] == "invite":
            LOG.info("received an invite")

            remoteOffer = RTCSessionDescription(sdp=message[1]['sdp'], type=message[1]['type'])
            pc = RTCPeerConnection()

            await pc.setRemoteDescription(remoteOffer)
            LOG.info("remote description set")

            # Aquire the media device
            video_player = MediaPlayer('/dev/video0', format='v4l2', options=options_video)
            audio_player = MediaPlayer("default", format="pulse")
            LOG.info("Media aquired")

            for t in pc.getTransceivers():
                LOG.debug(t.kind)
                if t.kind == "audio" and video_player.video:
                    pc.addTrack(video_player.video)
                if t.kind == "video" and audio_player.audio:
                    pc.addTrack(audio_player.audio)

            LOG.info("track added")

            LOG.info("generating answer...")
            answer = await pc.createAnswer()

            LOG.info("generated answer")

            await pc.setLocalDescription(answer)

            answer = pc.localDescription
            # LOG.debug(answer)

            answer_json = json.dumps({
                "sdp": answer.sdp,
                "type": answer.type
            })

            await sio.emit("ok", answer_json)

        if message[0] == "bye":
            LOG.info("End of the call")
            await sio.emit("bye", None)

            # Cleanup
            if pc:
                await pc.close()
            pc = None
            video_player = None
            video_player = None
            exit()


if __name__ == "__main__":
    server = HOST + ":" + str(PORT)

    LOG.info(f"connecting to {server}")

    asyncio.run(main(server))
