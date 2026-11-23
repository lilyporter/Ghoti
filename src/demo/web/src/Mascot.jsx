import React from 'react'

export default function Mascot({ small = false }) {
  return <svg className={small ? 'mascot mascot-small' : 'mascot'} viewBox="0 0 340 280" aria-hidden="true" focusable="false">
    <path d="M116 79c5-28 13-51 22-52 7-1 12 9 17 18 8-17 12-29 18-29 9 0 15 16 20 30 9-12 16-19 22-18 12 3 18 27 18 55Z" fill="#2d5ec1" />
    <path d="M253 126c22-19 42-29 51-18 8 10 2 30-6 45 12 20 19 43 7 53-13 11-34-3-53-20Z" fill="#2d5ec1" />
    <circle cx="171" cy="158" r="105" fill="#3978ea" />
    <circle cx="171" cy="158" r="74" fill="#aedcf8" />
    <path d="M90 140C62 113 40 118 29 137c-10 17-9 42 1 54 12 15 34 17 60-8Z" fill="#78bdf3" />
    <path d="M250 141c15-19 31-19 44-8 14 13 18 36 8 51-9 14-28 17-50 0Z" fill="#78bdf3" />
    <circle cx="139" cy="119" r="13" fill="#1c395b" />
    <circle cx="195" cy="119" r="13" fill="#1c395b" />
    <circle cx="136" cy="113" r="4.5" fill="white" />
    <circle cx="192" cy="113" r="4.5" fill="white" />
    <ellipse cx="120" cy="151" rx="13" ry="7" fill="#f19d89" />
    <ellipse cx="218" cy="151" rx="9" ry="6" fill="#f19d89" />
    <path d="M144 151c18 8 43 8 66-2-2 27-13 42-32 43-18 1-31-15-34-41Z" fill="#193855" />
    <path d="M150 153c16 5 36 5 55-1-3 8-11 11-27 11-14 0-23-3-28-10Z" fill="white" />
    <path d="M162 184c8-8 24-9 33-3-5 5-11 8-18 8-6 0-11-2-15-5Z" fill="#eb7f91" />
    <circle cx="101" cy="212" r="4" fill="#265fc9" />
    <circle cx="121" cy="222" r="4" fill="#265fc9" />
    <circle cx="142" cy="213" r="3.5" fill="#265fc9" />
    <circle cx="210" cy="205" r="3.5" fill="#265fc9" />
    <circle cx="232" cy="214" r="3.5" fill="#265fc9" />
    <circle cx="252" cy="204" r="4" fill="#265fc9" />
  </svg>
}
