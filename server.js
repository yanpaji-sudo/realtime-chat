const express=require('express');
const http=require('http');
const {Server}=require('socket.io');
const path=require('path');
const app=express();
const server=http.createServer(app);
const io=new Server(server);
app.use(express.static(path.join(__dirname,'public')));
const rooms=new Map();
const getRoom=id=>{if(!rooms.has(id))rooms.set(id,[]);return rooms.get(id)};
app.get('/chat/:roomId',(req,res)=>res.sendFile(path.join(__dirname,'public','index.html')));
app.get('/admin/:roomId',(req,res)=>res.sendFile(path.join(__dirname,'public','admin.html')));
io.on('connection',socket=>{
 socket.on('joinRoom',({roomId,role})=>{if(!roomId)return;socket.join(roomId);socket.data.roomId=roomId;socket.data.role=role==='admin'?'admin':'visitor';socket.emit('history',getRoom(roomId));});
 socket.on('sendMessage',text=>{const roomId=socket.data.roomId;if(!roomId||typeof text!=='string')return;const clean=text.trim().slice(0,2000);if(!clean)return;const m={id:Date.now()+'-'+Math.random().toString(36).slice(2),type:socket.data.role==='admin'?'admin':'visitor',text:clean,time:new Date().toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})};const room=getRoom(roomId);room.push(m);if(room.length>100)room.shift();io.to(roomId).emit('message',m);});
});
const PORT=process.env.PORT||3000;server.listen(PORT,'0.0.0.0',()=>console.log('Realtime chat running on '+PORT));
