import cv2
import asyncio
import json
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, MediaStreamTrack, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer, MediaRecorder

class WebcamStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        ret, frame = self.cap.read()
        if not ret:
            raise Exception("Could not read frame from webcam")

        # Convert frame to BGR format expected by VideoFrame
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame

async def signaling_client(pc):
    async with websockets.connect("ws://localhost:8765") as ws:
        async def send_message(message):
            await ws.send(json.dumps(message))

        async def receive_message():
            message = await ws.recv()
            return json.loads(message)

        # Create an offer and set local description
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await send_message({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})

        while True:
            message = await receive_message()
            if "sdp" in message:
                desc = RTCSessionDescription(sdp=message["sdp"], type=message["type"])
                await pc.setRemoteDescription(desc)
                if desc.type == "offer":
                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)
                    await send_message({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})
            elif "candidate" in message:
                candidate = RTCIceCandidate(
                    sdpMid=message["sdpMid"], sdpMLineIndex=message["sdpMLineIndex"], candidate=message["candidate"]
                )
                await pc.addIceCandidate(candidate)

async def run():
    pc = RTCPeerConnection()

    # Add local webcam stream
    player = MediaPlayer('/dev/video0', format='v4l2', options={'video_size': '640x480'})
    pc.addTrack(player.video)

    # Create signaling client
    signaling_task = asyncio.ensure_future(signaling_client(pc))

    @pc.on("track")
    async def on_track(track):
        print("Track received:", track.kind)
        if track.kind == "video":
            recorder = MediaRecorder('received_video.mp4')
            recorder.addTrack(track)
            await recorder.start()

    await signaling_task

if __name__ == "__main__":
    asyncio.run(run())
