import test from 'node:test';
import assert from 'node:assert/strict';
import { sampleFleetAt, CYCLE_SECONDS } from '../src/components/sampleFleetMotion.js';
const vehicles = Array.from({length:25}, (_,i) => ({id:i+1, vehicle_no:`SAMPLE-${String(i+1).padStart(3,'0')}`, type:'van', fuel_type:i%2?'Electric':'Diesel', load_capacity_kg:1000+i*10, reading:{fuel_percent:60+i, load_kg:500+i, odometer_km:10000+i*100}}));

test('only the existing 25 sample vehicles are animated; inputs stay unchanged', () => {
 const input=[...vehicles,{id:99,vehicle_no:'REAL-123',load_capacity_kg:1000}];
 const copy=JSON.stringify(input);
 const fleet=sampleFleetAt(input,0);
 assert.equal(fleet.length,25);
 assert.deepEqual(fleet.map(v=>v.id),vehicles.map(v=>v.id));
 assert.equal(JSON.stringify(input),copy);
});
test('all vehicles move during a cycle and stay within load/fuel bounds',()=>{
 for (const v of sampleFleetAt(vehicles,0)) {
  const positions=new Set();
  for(let t=0;t<CYCLE_SECONDS;t+=5){
   const state=sampleFleetAt(vehicles,t).find(row=>row.id===v.id);
   positions.add(`${state.lat},${state.lng}`);
   assert.ok(state.fuelPercent>=0 && state.fuelPercent<=100);
   assert.ok(state.loadKg>=0 && state.loadKg<=state.capacity);
  }
  assert.ok(positions.size>20);
 }
});
test('vehicle unloads, returns, reloads and continues on another cycle',()=>{
 const states=[0,45,65,105,165,185,225,240].map(t=>sampleFleetAt(vehicles,t)[0]);
 assert.equal(states[0].status,'Driving');
 assert.equal(states[1].status,'Delivering');
 assert.ok(states[1].loadKg<states[0].loadKg);
 assert.equal(states[5].status,'Returning');
 assert.equal(states[6].status,'Reloading');
 assert.equal(states[7].status,'Driving');
 assert.equal(states[7].delivered,3);
 assert.equal(states[7].loadKg,states[0].loadKg);
 assert.ok(states[7].odometerKm>states[0].odometerKm);
});
test('same elapsed time produces identical state for pause and empty fleet is supported',()=>{
 assert.deepEqual(sampleFleetAt(vehicles,30),sampleFleetAt(vehicles,30));
 assert.deepEqual(sampleFleetAt([],30),[]);
});
