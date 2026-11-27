// Layered raster cutouts driven by a small 2D skeleton; all units are logical pixels.
export class ElfRenderer {
  constructor(canvas, atlas, parts) {
    this.canvas=canvas;this.ctx=canvas.getContext('2d');this.atlas=atlas;this.parts=parts;
    canvas.width=480;canvas.height=480;this.ctx.setTransform(2,0,0,2,0,0);
  }
  part(index,x,y,w,h,rotation=0,pivot=.5) {
    const source=this.parts[index],c=this.ctx;
    c.save();c.translate(x,y);c.rotate(rotation);
    c.drawImage(this.atlas,source.x,source.y,source.w,source.h,-w/2,-h*pivot,w,h);c.restore();
  }
  segment(index,a,b,width,extension=0) {
    const dx=b[0]-a[0],dy=b[1]-a[1];
    this.part(index,a[0],a[1],width,Math.hypot(dx,dy)+extension,Math.atan2(-dx,dy),.05);
  }
  leg(side,hip,foot) {
    // Two-bone IK keeps the planted foot on the ground while the hips sway.
    const upper=34,lower=40,dx=foot[0]-hip[0],dy=foot[1]-hip[1],distance=Math.min(Math.hypot(dx,dy),upper+lower-.1);
    const angle=Math.atan2(dy,dx),bend=Math.acos(Math.max(-1,Math.min(1,(upper*upper+distance*distance-lower*lower)/(2*upper*distance))));
    const knee=[hip[0]+Math.cos(angle+(side===0?1:-1)*bend)*upper,hip[1]+Math.sin(angle+(side===0?1:-1)*bend)*upper];
    this.segment(side===0?9:10,hip,knee,15,4);
    this.segment(side===0?11:12,knee,[foot[0],foot[1]-7],20,9);
  }
  arm(side,x,y,angle,elbow) {
    const c=this.ctx;c.save();c.translate(x,y);c.rotate(angle);
    this.part(side===0?5:6,0,0,18,29,0,.1);
    c.translate(0,24);c.rotate(elbow);
    this.part(side===0?7:8,0,0,14,35,0,.07);c.restore();
  }
  draw(p) {
    const c=this.ctx;c.clearRect(0,0,240,240);
    c.save();c.globalAlpha=.13;c.fillStyle='#173c32';c.beginPath();c.ellipse(120+p.x*.3,225,35-p.lift*.35,4,0,0,Math.PI*2);c.fill();c.restore();
    c.save();c.translate(120+p.x,0);c.scale(Math.abs(p.turn)<.08?.08:p.turn,1);c.translate(-120,0);
    const rootY=150-p.lift;
    const flight=p.move==='hop'?p.lift:0;
    this.leg(0,[110+p.x*.1,rootY],[120+p.leftFoot[0],222-p.leftFoot[1]-flight]);
    this.leg(1,[130+p.x*.1,rootY],[120+p.rightFoot[0],222-p.rightFoot[1]-flight]);
    c.save();c.translate(120,rootY);c.rotate(p.lean);c.translate(-120,-150);
    this.part(1,120,83,65,88,p.hair);
    this.arm(0,102,105,p.leftArm,p.leftElbow);
    this.arm(1,138,105,p.rightArm,p.rightElbow);
    this.part(3,120,120,43,51);
    this.part(4,120,151,67,37,p.lean*.3);
    if (p.turn>=0) {
      this.part(0,120,77,56,59);
      this.part(13,120,54,57,30,p.hair*.3);
    } else this.part(1,120,77,62,72,p.hair*.3);
    this.part(2,120,43,66,41,p.hair*.18);
    this.part(14,139,23,24,37,-.5-p.hair,.1);
    this.part(15,95,79,13,53,p.hair*1.8,.12);
    c.restore();c.restore();
  }
}
