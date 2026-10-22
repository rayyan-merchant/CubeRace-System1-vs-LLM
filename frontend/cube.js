export const COLORS = {U:'#f7f7f2',R:'#e95c64',F:'#48b99a',D:'#f4cd58',L:'#ef9a50',B:'#5f91e8'};
export const SOLVED = [...'URFDLB'].map(f => f.repeat(9)).join('');

// Project the same 3D positions used by the engine. U row 0 meets B,
// U row 2 meets F; F column 2 meets R column 0.
const project = ([x,y,z]) => [95 + (x-z)*29, 89 - y*34 + (x+z)*15];
const pos = (face,r,c) => ({U:[c-1.5,1.5,r-1.5],F:[c-1.5,1.5-r,1.5],R:[1.5,1.5-r,1.5-c]})[face];
export function cubeSVG(state=SOLVED) {
  let content='';
  for(const face of ['U','F','R']) {
    for(let r=0;r<3;r++) for(let c=0;c<3;c++) {
      const points=[[r,c],[r,c+1],[r+1,c+1],[r+1,c]].map(([a,b])=>project(pos(face,a,b)).join(',')).join(' ');
      const index='URFDLB'.indexOf(face)*9+r*3+c;
      content+=`<polygon class="outline" data-face="${face}" data-index="${index}" points="${points}" fill="${COLORS[state[index]]}"><title>${face}${r*3+c+1}: ${state[index]}</title></polygon>`;
    }
  }
  return `<svg class="cube" viewBox="0 0 190 180" role="img" aria-label="Rubik's cube showing upper, front and right faces">${content}</svg>`;
}
export function cubeNet(state=SOLVED) {
  const origins={U:[0,3],L:[3,0],F:[3,3],R:[3,6],B:[3,9],D:[6,3]};
  let html='<div class="net" aria-label="All six faces in URFDLB net">';
  for(const f of 'URFDLB') for(let r=0;r<3;r++) for(let c=0;c<3;c++) {
    const [y,x]=origins[f], i='URFDLB'.indexOf(f)*9+r*3+c;
    html+=`<span data-color="${state[i]}" data-row="${y+r+1}" data-col="${x+c+1}" title="${f}${r*3+c+1}: ${state[i]}"></span>`;
  }
  return html+'</div>';
}
