import time
import random
import json
import asyncio
import aiomqtt
from enum import Enum
import sys
import os
from enum import Enum

student_id = "6420301001"

#class MachineStatus(Enum):
    #pressure = round(random.uniform(2000,3000), 2)
    #temperature = round(random.uniform(25.0,40.0), 2)
class MachineStatus():
    def __init__(self) -> None:
        self.pressure = round(random.uniform(2000,3000), 2)
        self.temperature = round(random.uniform(25.0,40.0), 2)
        self.water = round(random.uniform(0,100), 2)

#class MachineMaintStatus(Enum):
    #filter = random.choice(["clear", "clogged"])
    #noise = random.choice(["quiet", "noisy"])
class MachineMaintStatus:
    def __init__(self) -> None:
        self.filter = random.choice(["clear", "clogged"])
        self.noise = random.choice(["quiet", "noisy"])

class WashingMachine:
    def __init__(self, serial):
        self.MACHINE_STATUS = 'OFF'
        self.SERIAL = serial
    
    async def waiting(self):
        try:
            print(f'{time.ctime()} - Start')
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            print(f'{time.ctime()} - Waiting')
            raise

        print(f'{time.ctime()} - TIMEOUT')
        self.MACHINE_STATUS = 'FAULT'
        self.MACHINE_STATUS = 'TIMEOUT'
        print(f'{time.ctime()} - [{self.SERIAL}] STATUS: {self.MACHINE_STATUS}')
    
    async def waiting_task(self):
        self.task = asyncio.create_task(self.waiting())
        return self.task
    
    async def cancel_waiting(self):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            print(f'{time.ctime()} - Loading...')

async def publish_message(w, client, app, action, name, value):
    print(f"{time.ctime()} - [{w.SERIAL}] {name}:{value}")
    await asyncio.sleep(2)
    payload = {
                "action"    : "get",
                "project"   : student_id,
                "model"     : "model-01",
                "serial"    : w.SERIAL,
                "name"      : name,
                "value"     : value
            }
    print(f"{time.ctime()} - PUBLISH - [{w.SERIAL}] - {payload['name']} > {payload['value']}")
    await client.publish(f"v1cdti/{app}/{action}/{student_id}/model-01/{w.SERIAL}"
                        , payload=json.dumps(payload))

async def CoroWashingMachine(w, sensor, client):
    while True:
        wait_next = round(10*random.random(),2)
        print(f"{time.ctime()} - [{w.SERIAL}-{w.MACHINE_STATUS}] Waiting to start... {wait_next} seconds.")
        await asyncio.sleep(wait_next)
        if w.MACHINE_STATUS == 'OFF':
            continue
        if w.MACHINE_STATUS == 'READY':
            print(f"{time.ctime()} - [{w.SERIAL}-{w.MACHINE_STATUS}]")
            await publish_message(w, client, 'app', 'get', 'STATUS', 'READY')
            await publish_message(w, client, 'app', 'get', 'DOOR', 'CLOSE')
            w.MACHINE_STATUS = 'FILLWATER'
            await publish_message(w, client, 'app', 'get', 'STATUS', 'Wait for water')
            task = w.waiting_task()
            await task

        if w.MACHINE_STATUS == 'HEATWATER':
            await publish_message(w, client, 'app', 'get', 'FAULT', w.FAULT_TYPE)
            while w.MACHINE_STATUS == 'FAULT':
                print(f"{time.ctime()} - [{w.SERIAL}] Waiting to clear status")
                await asyncio.sleep(1)
            
        if w.MACHINE_STATUS == 'HEATWATER':
            task = w.waiting_task()
            await task
            while w.MACHINE_STATUS == 'HEATWATER':
                await asyncio.sleep(2)
            
        if w.MACHINE_STATUS == 'WASH':
            continue

async def listen(w, sensor, client):
    async with client.messages() as messages:
        await client.subscribe(f"v1cdti/hw/set/{student_id}/model-01/{w.SERIAL}")
        async for message in messages:
            m_decode = json.loads(message.payload)
            if message.topic.matches(f"v1cdti/hw/set/{student_id}/model-01/{w.SERIAL}"):
                # set washing machine status
                print(f"{time.ctime()} - MQTT - [{m_decode['serial']}]:{m_decode['name']} => {m_decode['value']}")
                if (m_decode['name']=="STATUS" and m_decode['value']=="READY"):
                    w.MACHINE_STATUS = 'READY'
                if m_decode['name'] == "STATUS":
                    w.MACHINE_STATUS = m_decode['value']

                if w.MACHINE_STATUS == 'FILLWATER':
                    if m_decode['name'] == "LEVEL":
                        sensor.fulldetect = m_decode['value']
                        if sensor.fulldetect == 'FULL':
                            w.MACHINE_STATUS = 'HEATWATER'
                            print(f'{time.ctime()} - [{w.SERIAL}] STATUS: {w.MACHINE_STATUS}')
                            await publish_message(w, client, 'hw', 'get', 'STATUS', w.MACHINE_STATUS)
                        await w.cancel_waiting()
                
                if w.MACHINE_STATUS == 'HEATWATER':
                    if m_decode['name'] == "Temp":
                        sensor.heatreach == m_decode['value']
                        if sensor.heatreach == 'REACH':
                            w.MACHINE_STATUS = 'WASH'
                            print(f'{time.ctime()} - [{w.SERIAL}] STATUS: {w.MACHINE_STATUS}')
                            await publish_message(w, client, 'hw', 'get', 'STATUS', w.MACHINE_STATUS)
                        await w.cancel_waiting()
                
                if m_decode['name'] == "FAULT":
                    if m_decode['value'] == 'CLEAR':
                            w.MACHINE_STATUS = 'OFF'
                            await publish_message(w, client, 'hw', 'get', 'STATUS', w.MACHINE_STATUS)

async def main():
    w = WashingMachine(serial='SN-001')
    sensor = MachineStatus()
    async with aiomqtt.Client("broker.hivemq.com") as client:
        await asyncio.gather(listen(w, sensor, client) , CoroWashingMachine(w, sensor, client))

if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    from asyncio import set_event_loop_policy, WindowsSelectorEventLoopPolicy
    set_event_loop_policy(WindowsSelectorEventLoopPolicy())
asyncio.run(main())
