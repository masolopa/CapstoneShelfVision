export type Point = [number, number];
const cross = (a:Point,b:Point,c:Point) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
export function validPolygon(points:Point[]):boolean {
  if(points.length<3) return false;
  const area=points.reduce((sum,a,i)=>{const b=points[(i+1)%points.length];return sum+a[0]*b[1]-b[0]*a[1];},0);
  if(Math.abs(area)<1e-8) return false;
  for(let i=0;i<points.length;i++){
    const a=points[i], b=points[(i+1)%points.length];
    if(Math.hypot(a[0]-b[0],a[1]-b[1])<1e-6) return false;
    for(let j=i+1;j<points.length;j++){
      if(j===i+1 || (i===0 && j===points.length-1)) continue;
      const c=points[j],d=points[(j+1)%points.length];
      const within=(p:Point,q:Point,r:Point)=>Math.abs(cross(p,q,r))<1e-10 && r[0]>=Math.min(p[0],q[0])-1e-10 && r[0]<=Math.max(p[0],q[0])+1e-10 && r[1]>=Math.min(p[1],q[1])-1e-10 && r[1]<=Math.max(p[1],q[1])+1e-10;
      if((cross(a,b,c)*cross(a,b,d)<0 && cross(c,d,a)*cross(c,d,b)<0)||within(a,b,c)||within(a,b,d)||within(c,d,a)||within(c,d,b))return false;
    }
  }
  return true;
}
export function moveHandle(points:Point[],index:number,edge:boolean,dx:number,dy:number):Point[]{
  const indices=edge?[index,(index+1)%points.length]:[index];
  dx=Math.max(Math.max(...indices.map(i=>-points[i][0])),Math.min(dx,Math.min(...indices.map(i=>1-points[i][0]))));
  dy=Math.max(Math.max(...indices.map(i=>-points[i][1])),Math.min(dy,Math.min(...indices.map(i=>1-points[i][1]))));
  return points.map((point,i)=>indices.includes(i)?[point[0]+dx,point[1]+dy]:[...point]);
}
