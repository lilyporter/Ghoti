import React from 'react'

export default function WordArt({ word }) {
  let art
  switch (word) {
    case 'sun':
      art = <><circle cx="200" cy="200" r="134" fill="#fff1c4"/>{[0,45,90,135,180,225,270,315].map(a => <rect key={a} x="194" y="75" width="12" height="32" rx="6" fill="#ecb635" transform={`rotate(${a} 200 200)`}/>)}<circle cx="200" cy="200" r="79" fill="#f9d776"/><ellipse cx="171" cy="148" rx="23" ry="10" transform="rotate(-30 171 148)" fill="#ffecad"/><path d="M77 282c0-17 14-29 30-29 8-20 36-23 48-2 18-2 33 11 33 29 0 13-11 22-24 22H100c-14 0-23-8-23-20Zm219-76c0-16 13-28 29-28 8-20 36-23 48-2 17-2 29 11 29 28 0 13-10 22-23 22h-59c-14 0-24-8-24-20Z" fill="white"/></>
      break
    case 'gift':
      art = <><circle cx="200" cy="200" r="135" fill="#fff1d5"/><rect x="106" y="178" width="188" height="145" rx="15" fill="#f19a85"/><rect x="94" y="161" width="212" height="45" rx="12" fill="#ed816f"/><rect x="184" y="161" width="32" height="162" fill="#ffd973"/><path d="M198 162c-61-10-73-61-44-68 22-6 42 26 44 68Zm4 0c60-10 73-61 44-68-22-6-42 26-44 68Z" fill="none" stroke="#e9ae43" strokeWidth="14" strokeLinecap="round"/><circle cx="200" cy="164" r="17" fill="#ffd973"/></>
      break
    case 'seal':
      art = <><circle cx="200" cy="200" r="135" fill="#dff4f6"/><ellipse cx="190" cy="265" rx="102" ry="48" fill="#8fc7d8"/><path d="M111 263c-24 8-35 30-18 35 14 4 33-10 50-21m129-14c24 8 35 30 18 35-14 4-33-10-50-21" fill="#74b5ce"/><circle cx="205" cy="177" r="72" fill="#a9d9e7"/><ellipse cx="178" cy="172" rx="7" ry="9" fill="#253f58"/><ellipse cx="232" cy="172" rx="7" ry="9" fill="#253f58"/><ellipse cx="205" cy="198" rx="12" ry="9" fill="#32465b"/><path d="M205 207q-14 17-27 5m27-5q14 17 27 5" fill="none" stroke="#32465b" strokeWidth="4" strokeLinecap="round"/><path d="M176 201l-45-9m43 16-43 7m102-14 45-9m-43 16 43 7" stroke="#6da6bf" strokeWidth="3" strokeLinecap="round"/></>
      break
    case 'sheep':
      art = <><circle cx="200" cy="200" r="135" fill="#e8f4d9"/><path d="M137 264v37m97-37v37" stroke="#a98573" strokeWidth="18" strokeLinecap="round"/>{[[130,205],[153,173],[188,159],[225,165],[254,185],[264,222],[232,251],[189,257],[149,244]].map(([x,y])=><circle key={`${x}-${y}`} cx={x} cy={y} r="32" fill="white"/>)}<ellipse cx="214" cy="210" rx="48" ry="42" fill="#eac6a5"/><ellipse cx="173" cy="193" rx="15" ry="10" fill="#dba980"/><ellipse cx="255" cy="193" rx="15" ry="10" fill="#dba980"/><circle cx="197" cy="204" r="4" fill="#3d4b54"/><circle cx="231" cy="204" r="4" fill="#3d4b54"/><path d="M207 226q8 8 16 0" fill="none" stroke="#9a7162" strokeWidth="4" strokeLinecap="round"/></>
      break
    case 'shell':
      art = <><circle cx="200" cy="200" r="135" fill="#e7f3f5"/><path d="M200 293C134 272 92 217 119 167c10-18 30-29 51-18 17-24 44-23 60 0 23-9 43 5 48 27 11 52-28 96-78 117Z" fill="#f8b6a1" stroke="#e88e82" strokeWidth="5"/><path d="M200 291 133 170m67 121-31-135m31 135 9-137m-9 137 46-125m-46 125 72-108" stroke="#eb9188" strokeWidth="5" strokeLinecap="round"/><path d="M167 285q34 12 66-1" fill="none" stroke="#e98d80" strokeWidth="11" strokeLinecap="round"/></>
      break
    case 'ship':
      art = <><circle cx="200" cy="200" r="135" fill="#def3f8"/><path d="M94 274q22-13 44 0t44 0t44 0t44 0t44 0" fill="none" stroke="#75c9df" strokeWidth="10" strokeLinecap="round"/><path d="M97 225h211l-25 45H132Z" fill="#e98770"/><path d="M198 106v119" stroke="#93664f" strokeWidth="7"/><path d="M188 112 114 205h74Zm19 7 80 85h-80Z" fill="#fff9e8" stroke="#e7c898" strokeWidth="4"/><circle cx="151" cy="246" r="7" fill="#ffdf89"/><circle cx="201" cy="246" r="7" fill="#ffdf89"/><circle cx="251" cy="246" r="7" fill="#ffdf89"/></>
      break
    case 'shoe':
      art = <><circle cx="200" cy="200" r="135" fill="#e8f2dc"/><path d="M81 227q42 4 70-30l19-31 32 10q11 37 34 45l52 17q27 9 27 36H80q-11-25 1-47Z" fill="#73b6ec" stroke="#438bd8" strokeWidth="5"/><path d="M83 270h232v20H84q-9 0-9-10t8-10Z" fill="white" stroke="#438bd8" strokeWidth="4"/><path d="m156 200 56 10m-49 3 53 10m-43 2 47 10" stroke="white" strokeWidth="7" strokeLinecap="round"/><path d="M90 244q22 8 42 0" fill="none" stroke="#9ed3f4" strokeWidth="8" strokeLinecap="round"/></>
      break
    case 'shop':
      art = <><circle cx="200" cy="200" r="135" fill="#fff1d6"/><rect x="101" y="154" width="198" height="158" rx="8" fill="#aad7e6"/><rect x="124" y="213" width="58" height="72" rx="5" fill="#e9f8fb"/><rect x="217" y="211" width="55" height="101" rx="5" fill="#fff8ed"/><circle cx="260" cy="265" r="4" fill="#e9a76e"/><path d="M93 152h214l-11 52H104Z" fill="#f29c83"/>{[117,153,189,225,261].map(x=><path key={x} d={`M${x} 153h22l7 51h-36Z`} fill="#fff7e7"/>)}<path d="M129 129h142" stroke="#e3b253" strokeWidth="12" strokeLinecap="round"/></>
      break
    case 'soup':
      art = <><circle cx="200" cy="200" r="135" fill="#fff1d5"/><path d="M151 134q-17-17 0-35m49 35q-17-17 0-35m49 35q-17-17 0-35" fill="none" stroke="#a9d5db" strokeWidth="8" strokeLinecap="round"/><path d="M93 197h214q-3 91-107 91T93 197Z" fill="#f1a486"/><ellipse cx="200" cy="196" rx="107" ry="28" fill="#fff7e8"/><ellipse cx="200" cy="194" rx="89" ry="17" fill="#e6bf78"/><path d="M121 280h158" stroke="#d9816b" strokeWidth="12" strokeLinecap="round"/><path d="M261 160q38-25 59-2" fill="none" stroke="#9ab6b7" strokeWidth="8" strokeLinecap="round"/></>
      break
    case 'chute':
      art = <><circle cx="200" cy="200" r="135" fill="#e6f3dc"/><path d="M114 285V142h73" fill="none" stroke="#3979d9" strokeWidth="15" strokeLinecap="round" strokeLinejoin="round"/><path d="M114 178h68m-68 36h67m-67 36h61" stroke="#78b6ec" strokeWidth="8" strokeLinecap="round"/><path d="M179 140q5 87 46 100t72 12v28q-78 8-113-37-32-42-34-103Z" fill="#f1a182" stroke="#db7d69" strokeWidth="5"/><path d="M90 286h230" stroke="#84cabb" strokeWidth="10" strokeLinecap="round"/></>
      break
    default:
      art = <circle cx="200" cy="200" r="135" fill="#dff3f7"/>
  }
  return <svg viewBox="0 0 400 400" role="img" aria-label={`Illustration of ${word}`}>
    {art}
  </svg>
}
