/** Display-only largest-remainder rounding, in tenths of a percent. */
export function surfacePercentageTenths(pixels: readonly number[]): number[] {
  const values=pixels.map(value=>Number.isFinite(value) && value>0 ? value : 0);
  const total=values.reduce((sum,value)=>sum+value,0);
  if(!total)return values.map(()=>0);
  const exact=values.map(value=>value/total*1000);
  const rounded=exact.map(Math.floor);
  const order=exact.map((value,index)=>({index,remainder:value-rounded[index]}))
    .filter(item=>values[item.index]>0)
    .sort((a,b)=>b.remainder-a.remainder || a.index-b.index);
  const missing=1000-rounded.reduce((sum,value)=>sum+value,0);
  for(let i=0;i<missing;i++)rounded[order[i % order.length].index]++;
  return rounded;
}
