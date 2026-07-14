const http=require("http"),fs=require("fs"),path=require("path");
const dir="C:\\AriaNg-Web";
http.createServer((req,res)=>{
  const f=path.join(dir,req.url==="/"?"index.html":req.url);
  fs.readFile(f,(err,data)=>{
    if(err){res.writeHead(404);res.end("not found")}
    else{res.writeHead(200,{"Content-Type":"text/html","Access-Control-Allow-Origin":"*"});res.end(data)}
  });
}).listen(16801,()=>console.log("AriaNg web em http://127.0.0.1:16801"));
