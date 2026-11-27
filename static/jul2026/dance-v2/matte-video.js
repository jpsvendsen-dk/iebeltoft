// Decode an ordinary H.264 movie with RGB on its left and an alpha mask on
// its right. This avoids relying on platform-specific transparent video codecs.
export class MatteVideo {
  constructor(video,canvas,info){
    this.video=video;this.canvas=canvas;this.info=info;this.callback=null;this.listeners=[];
    canvas.width=info.width;canvas.height=info.height;
    this.context=canvas.getContext('2d');
    this.mask=document.createElement('canvas');
    this.mask.width=info.width;this.mask.height=info.height;
    this.maskContext=this.mask.getContext('2d',{willReadFrequently:true});
    // Capture the packed frame ONCE before reading pixels. A playing video may
    // advance while getImageData waits for the GPU, otherwise RGB and mask can
    // come from different frames and produce colored outlines during motion.
    this.packed=document.createElement('canvas');
    this.packed.width=info.width*2;this.packed.height=info.height;
    this.packedContext=this.packed.getContext('2d');
    this.draw=this.draw.bind(this);this.tick=this.tick.bind(this);
    const on=(target,event,handler)=>{target.addEventListener(event,handler);this.listeners.push([target,event,handler]);};
    for(const event of ['loadeddata','seeked','pause'])on(video,event,this.draw);
    on(video,'play',()=>{this.stop();this.tick();});
    on(video,'pause',()=>this.stop());
    on(document,'visibilitychange',()=>{this.stop();if(!document.hidden&&!video.paused)this.tick();});
    video.src=info.src;video.loop=Boolean(info.loop);video.load();
  }
  draw(){
    if(this.video.readyState<2)return;
    const {width:w,height:h}=this.info;
    this.packedContext.drawImage(this.video,0,0,w*2,h);
    const mask=this.maskContext;
    mask.drawImage(this.packed,w,0,w,h,0,0,w,h);
    const pixels=mask.getImageData(0,0,w,h);
    for(let i=0;i<pixels.data.length;i+=4)pixels.data[i+3]=pixels.data[i];
    mask.putImageData(pixels,0,0);
    const c=this.context;
    c.globalCompositeOperation='source-over';c.clearRect(0,0,w,h);
    c.drawImage(this.packed,0,0,w,h,0,0,w,h);
    c.globalCompositeOperation='destination-in';c.drawImage(this.mask,0,0);
    c.globalCompositeOperation='source-over';
  }
  tick(){
    this.callback=null;this.draw();
    if(this.video.paused||document.hidden)return;
    this.callback=this.video.requestVideoFrameCallback?this.video.requestVideoFrameCallback(this.tick):requestAnimationFrame(this.tick);
  }
  stop(){
    if(this.callback===null)return;
    if(this.video.cancelVideoFrameCallback)this.video.cancelVideoFrameCallback(this.callback);
    else cancelAnimationFrame(this.callback);
    this.callback=null;
  }
  dispose(){this.stop();this.video.pause();for(const [target,event,handler] of this.listeners)target.removeEventListener(event,handler);this.listeners=[];}
}
