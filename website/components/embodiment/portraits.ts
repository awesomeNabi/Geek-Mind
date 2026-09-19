/** Curved SVG shells for the reference camera. Hand-drawn from observation;
 * these are editable geometric paths, not image traces or embedded frames. */
import type { ArmPose, DogPose } from "./robots";
import { bodyRise, portraitCamera, solveLeg, type LegName } from "./rig";

export function portraitDefs(id: string) {
  return `<defs>
    <linearGradient id="${id}-shell" x1=".18" y1="0" x2=".76" y2="1" gradientUnits="objectBoundingBox"><stop stop-color="#e0e4e6"/><stop offset=".27" stop-color="#c7cdd1"/><stop offset=".58" stop-color="#a7afb6"/><stop offset=".85" stop-color="#bbc2c7"/><stop offset="1" stop-color="#8b949c"/></linearGradient>
    <linearGradient id="${id}-side" x1="0" y1="0" x2=".28" y2="1"><stop stop-color="#d4d9dc"/><stop offset=".46" stop-color="#b9c1c7"/><stop offset="1" stop-color="#848e98"/></linearGradient>
    <linearGradient id="${id}-limb" x1="0" y1=".4" x2="1" y2=".5"><stop stop-color="#7f8991"/><stop offset=".22" stop-color="#c4cbd0"/><stop offset=".48" stop-color="#dce0e2"/><stop offset=".76" stop-color="#b6bec5"/><stop offset="1" stop-color="#929da6"/></linearGradient>
    <linearGradient id="${id}-motor" x1="0" y1=".2" x2="1" y2=".5"><stop stop-color="#818d96"/><stop offset=".16" stop-color="#d8dfe3"/><stop offset=".37" stop-color="#c8d0d6"/><stop offset=".7" stop-color="#aeb9c1"/><stop offset="1" stop-color="#7d8993"/></linearGradient>
    <radialGradient id="${id}-cap" cx=".28" cy=".17" r=".9"><stop stop-color="#d6dde1"/><stop offset=".45" stop-color="#b6bfc6"/><stop offset=".82" stop-color="#99a5ae"/><stop offset="1" stop-color="#79868f"/></radialGradient>
    <linearGradient id="${id}-black" x1="0" y1="0" x2=".7" y2="1"><stop stop-color="#464d51"/><stop offset=".45" stop-color="#151c20"/><stop offset=".7" stop-color="#080d10"/><stop offset="1" stop-color="#373e41"/></linearGradient>
    <radialGradient id="${id}-glass" cx=".36" cy=".28"><stop stop-color="#415667"/><stop offset=".3" stop-color="#101a22"/><stop offset=".66" stop-color="#03080d"/><stop offset=".82" stop-color="#26343e"/><stop offset="1" stop-color="#030609"/></radialGradient>
    <linearGradient id="${id}-tire" x1="0" y1=".3" x2="1" y2=".6"><stop stop-color="#414649"/><stop offset=".25" stop-color="#202628"/><stop offset=".53" stop-color="#33393b"/><stop offset=".75" stop-color="#151a1d"/><stop offset="1" stop-color="#080d0f"/></linearGradient>
    <radialGradient id="${id}-rim" cx=".7" cy=".35"><stop stop-color="#8b959a"/><stop offset=".45" stop-color="#b4bdc2"/><stop offset=".65" stop-color="#e4e8ea"/><stop offset=".74" stop-color="#bcc6cc"/><stop offset=".93" stop-color="#77858d"/><stop offset="1" stop-color="#151c21"/></radialGradient>
    <linearGradient id="${id}-gunmetal" x1="0" y1=".1" x2="1" y2=".5"><stop stop-color="#171819"/><stop offset=".19" stop-color="#414345"/><stop offset=".43" stop-color="#252729"/><stop offset=".71" stop-color="#151617"/><stop offset="1" stop-color="#4b4d4e"/></linearGradient>
    <linearGradient id="${id}-alloy" x1="0" y1="0" x2="1" y2=".75"><stop stop-color="#a8aaab"/><stop offset=".32" stop-color="#828587"/><stop offset=".56" stop-color="#686b6d"/><stop offset=".72" stop-color="#969899"/><stop offset="1" stop-color="#484b4e"/></linearGradient>
    <radialGradient id="${id}-joint"><stop stop-color="#3c3e3f"/><stop offset=".66" stop-color="#292b2c"/><stop offset=".78" stop-color="#4a4c4d"/><stop offset=".86" stop-color="#222425"/><stop offset="1" stop-color="#646667"/></radialGradient>
  </defs>`;
}
const screw = (x: number, y: number, rx = 3, ry = 4) =>
  `<ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="#555f65"/><ellipse cx="${x + 0.6}" cy="${y - 0.4}" rx="${rx * 0.48}" ry="${ry * 0.54}" fill="#bdc5c9"/><path d="M${x - 1} ${y + 1}l2 -2" stroke="#4b565e" stroke-width=".9"/>`;
function tire(id: string, x: number, y: number, scale: number, spin: number, near: boolean) {
  const treadId = `${id}-tread-${x}-${y}`;
  const grooves = Array.from({ length: 22 }, (_, i) => {
    const a = (i * Math.PI) / 11 + spin;
    const cy = Math.sin(a) * 57,
      cx = Math.cos(a) * 34;
    return `<path d="M${cx - 12} ${cy - 3}l18 -8m-7 4l8 4" stroke="#070e11" stroke-opacity=".55" stroke-width="1.7" transform="rotate(-11)"/>`;
  }).join("");
  return `<g transform="translate(${x} ${y}) scale(${scale}) rotate(13)">
    <ellipse cx="-9" rx="41" ry="64" fill="url(#${id}-tire)"/>
    <path d="M-16 -62C-62 -58 -65 43 -27 62L3 64C-35 51 -34 -47 3 -62Z" fill="url(#${id}-tire)"/>
    <defs><clipPath id="${treadId}"><ellipse cx="-9" rx="41" ry="64"/></clipPath></defs><g clip-path="url(#${treadId})">${grooves}</g><ellipse cx="8" rx="36" ry="64" fill="#181e21"/>
    <ellipse cx="9" rx="30" ry="56" fill="none" stroke="#485054" stroke-width="1.7"/>
    <ellipse cx="10" rx="24" ry="43" fill="url(#${id}-rim)"/>
    <ellipse cx="11" rx="14" ry="29" fill="#b2bcc3"/><ellipse cx="13" rx="8" ry="20" fill="#89979f"/>
    ${near ? '<ellipse cx="14" cy="19" rx="2.7" ry="4" fill="#1d272e"/>' : ""}
    <path d="M11 -39C-8 -40 -17 -10 -10 19" fill="none" stroke="#e2e8eb" stroke-width="2" opacity=".7"/>
  </g>`;
}
function lowerLeg(id: string, kind: "front" | "rear" | "farFront" | "farRear", pose: DogPose) {
  const rig = solveLeg(kind, pose);
  const [kx, ky] = rig.knee,
    [fx, fy] = rig.foot;
  const near = kind === "front" || kind === "rear";
  const dx = fx - kx,
    dy = fy - ky;
  const leg = `M${kx - 7} ${ky - 3} C${kx - 21} ${ky + dy * 0.2} ${fx + 13} ${fy - dy * 0.35} ${fx - 11} ${fy - 37} Q${fx - 17} ${fy - 12} ${fx - 24} ${fy + 5} Q${fx - 5} ${fy + 24} ${fx + 27} ${fy + 10} L${fx + 24} ${fy - 19} C${fx + 13} ${fy - dy * 0.36} ${kx + 31} ${ky + dy * 0.2} ${kx + 18} ${ky + 1}Z`;
  const [wheelX, wheelY] = rig.wheel;
  const wx = wheelX + 6,
    wy = wheelY + 40,
    wheely = wheelY;
  return `<g>
    <g opacity="${pose.footOpacity}"><path d="${leg}" fill="url(#${id}-limb)" stroke="#8d989f" stroke-width=".7"/>
      <path d="M${kx + 7} ${ky + 16}Q${kx + dx * 0.2} ${ky + dy * 0.25} ${fx + 3} ${fy - 50}" fill="none" stroke="#e0e5e7" stroke-width="4" opacity=".65"/>
      <path d="M${kx - 6} ${ky + 18}L${kx + dx * 0.45 - 8} ${ky + dy * 0.46}L${kx + dx * 0.45 + 8} ${ky + dy * 0.42}Z" fill="#77838c"/>
      <path d="M${fx - 22} ${fy - 2}Q${fx + 3} ${fy + 9} ${fx + 27} ${fy + 1}L${fx + 27} ${fy + 13}Q${fx + 24} ${fy + 33} ${fx} ${fy + 30}Q${fx - 26} ${fy + 29} ${fx - 26} ${fy + 12}Z" fill="url(#${id}-black)"/>
      <path d="M${fx - 13} ${fy - 17}q11 5 34 1" fill="none" stroke="#77828a" stroke-width="1"/>
      ${screw(fx - 5, fy - 10, 2.6, 4)}${screw(fx + 17, fy - 7, 2.2, 3.6)}
    </g>
    <g opacity="${pose.wheelOpacity}">
      ${near ? "" : tire(id, wx - 6, wheely, 1.48, pose.spin, false)}
      <path d="M${kx - 12} ${ky + 3} Q${kx - 55} ${ky + 65} ${wx + 25} ${wy - 75} Q${wx + 5} ${wy - 45} ${wx + 1} ${wy - 32} L${wx + 34} ${wy - 17} Q${wx + 37} ${wy - 55} ${wx + 58} ${wy - 85} Q${kx + 5} ${ky + 65} ${kx + 18} ${ky + 3}Z" fill="url(#${id}-limb)" stroke="#98a3aa" stroke-width=".8"/>
      <path d="M${kx} ${ky + 20} Q${kx - 40} ${ky + 68} ${wx + 38} ${wy - 76} Q${wx + 21} ${wy - 52} ${wx + 20} ${wy - 30} L${wx + 35} ${wy - 26} Q${wx + 35} ${wy - 58} ${wx + 51} ${wy - 84} Q${kx} ${ky + 63} ${kx + 7} ${ky + 18}Z" fill="#7a868d"/>
      <ellipse cx="${wx + 12}" cy="${wy - 20}" rx="22" ry="31" fill="url(#${id}-motor)" transform="rotate(15 ${wx + 12} ${wy - 20})"/>
      ${screw(wx + 20, wy - 40, 2.2, 3.1)}${screw(wx + 13, wy + 1, 2.2, 3.1)}

      ${near ? tire(id, wx - 6, wheely, 1.55, pose.spin, true) : ""}
    </g>
  </g>`;
}
function farRearShell(_id: string) {
  return `<path d="M654 175Q624 188 642 251L679 319L692 355Q705 372 723 352L717 315L695 226Z"/>`;
}

function farFrontShell(_id: string) {
  return `<path d="M341 198C292 186 266 230 282 279L330 356L344 427L346 478Q349 523 375 521Q397 516 392 485L378 403L366 318L378 241Z"/>
      <path d="M348 419L351 484L365 470L366 431Z" fill="#515c62"/>`;
}

function torsoShell(id: string) {
  return `<path d="M461 320Q515 357 551 358L589 375L633 351L753 314L797 263L737 209Z" fill="url(#${id}-black)"/>
    <path d="M581 350l-19 3 4 25q26 17 39 -5l-2 -29m137 -63l-6 22q28 13 39 -11l-1 -24" fill="#39434a"/>
    <path d="M354 199C390 181 409 176 431 164Q457 140 488 151Q526 166 555 154L620 135Q639 100 663 103L702 113L748 112Q770 114 780 140L807 131L857 143Q886 142 906 154L918 224L835 255Q827 273 820 281L609 357L491 319Z" fill="url(#${id}-shell)" stroke="#aab2b7" stroke-width="1"/>
    <path d="M491 231Q503 180 542 192Q579 195 607 225L681 207L805 166Q823 156 834 139L817 191L823 259Q824 282 802 291L619 351Q611 297 586 257Q560 213 491 231Z" fill="url(#${id}-side)"/>
    <path d="M489 232Q502 193 536 200Q576 205 601 240L574 268L488 277Z" fill="url(#${id}-black)"/>
    <path d="M354 198Q404 181 455 175L495 161M492 181Q522 175 548 174L624 151M637 128Q650 99 667 109" stroke="#e2e6e8" stroke-width="2" fill="none" opacity=".55"/>
    <path d="M573 165L677 135L713 141L603 173Z" fill="#949fa7"/>
    <path d="M623 136Q637 106 662 105L684 112Q650 108 642 133Z" fill="url(#${id}-limb)"/>
    <path d="M427 184q18 -12 35 -8l3 7q-15 9 -31 7Z" fill="#a2adb5"/>
    <path d="M686 227L777 194Q785 192 787 201L792 265Q792 276 783 280L683 316" fill="none" stroke="#78848e" stroke-width="1.2"/>
    <path d="M690 230L777 199" fill="none" stroke="#e3e8ea" opacity=".65"/>
    <g transform="matrix(.91 -.30 .05 1 638 216)"><text font-family="Arial,sans-serif" font-weight="800" font-size="31" letter-spacing="-.8" fill="#f5f7f6">UNITREE</text></g>
    <g transform="skewY(-17)"><rect x="709" y="468" width="17" height="38" rx="4" fill="#7b8790"/><rect x="712" y="471" width="10" height="31" rx="3" fill="#253038"/><path d="M715 473v25" stroke="#929ea6" stroke-width="2"/><rect x="752" y="468" width="17" height="38" rx="4" fill="#7b8790"/><rect x="755" y="471" width="10" height="31" rx="3" fill="#26313b"/><rect x="735" y="437" width="12" height="27" rx="6" fill="#8997a1"/><path d="M739 440v14" stroke="#667783" stroke-width="3"/>${[0, 1, 2, 3].map((j) => `<rect x="738" y="${472 + j * 7}" width="2.5" height="4" fill="#a7c792"/>`).join("")}</g>
    <path d="M353 201Q309 184 292 214Q282 231 282 252L308 272L324 256Z" fill="url(#${id}-cap)"/>
    <path d="M327 211Q318 231 314 248L294 254L282 250" fill="none" stroke="#697983" stroke-width="1.5"/>
    ${screw(335, 221, 2, 3)}
    <path d="M485 234Q499 219 520 224L562 237Q596 247 608 277L610 329Q598 350 575 362L527 365Q494 361 480 337Q467 304 478 266Z" fill="url(#${id}-motor)" stroke="#8c989f" stroke-width="1"/>
    <path d="M516 231Q493 279 505 331Q511 351 526 361M549 239Q526 284 539 335Q545 351 557 364" fill="none" stroke="#778791" stroke-width="1.2"/>
    <path d="M522 234Q505 275 512 320" fill="none" stroke="#e3e9ec" stroke-width="6" opacity=".75"/>
    ${[screw(516, 260, 1.8, 2.5), screw(525, 299, 1.8, 2.8), screw(543, 350, 1.8, 2.5)].join("")}`;
}

function frontShell(id: string) {
  return `<path d="M550 244Q579 234 606 255Q628 265 644 286Q665 295 666 319L673 340Q718 367 755 414Q770 435 770 458Q768 477 753 477Q737 473 738 454Q725 425 695 405L627 373Q599 376 578 358Q556 336 551 309Q546 278 550 244Z" fill="url(#${id}-shell)" stroke="#9ba7ae" stroke-width="1"/>
    <path d="M608 265Q642 271 658 302Q669 322 652 340Q638 359 610 354Q593 350 590 329Q588 295 608 265Z" fill="url(#${id}-cap)"/>
    <path d="M624 373Q673 377 709 410L737 450L731 427Q715 394 668 363" fill="#a0adb5"/>
    <path d="M711 423L725 431L740 458L736 436L722 420Z" fill="#4b5962"/>
    ${screw(763, 458, 4, 6)}${screw(616, 359, 3.3, 4.1)}`;
}

function rearShell(id: string) {
  return `<path d="M837 146Q881 136 911 156Q931 166 945 192Q962 219 956 233L953 259Q970 341 974 413L973 446Q970 466 956 470Q940 468 942 448L939 409Q930 336 909 286L892 267Q864 272 846 252Q827 232 825 202Q826 169 837 146Z" fill="url(#${id}-shell)" stroke="#96a2aa" stroke-width="1"/>
    <path d="M838 147Q824 175 830 213L844 237M863 146Q847 174 849 214Q856 248 885 262" fill="none" stroke="#84929b" stroke-width="1.2"/>
    <path d="M889 157Q922 157 941 187Q953 206 956 221Q951 238 934 235L892 215Q879 197 889 157Z" fill="url(#${id}-cap)"/>
    <path d="M946 391L942 427L951 440L958 404Z" fill="#5c6971"/>
    <path d="M947 396L948 422L953 411" stroke="#b9c4c9" stroke-width="3" fill="none"/>
    ${screw(959, 452, 4, 5)}${screw(910, 238, 3, 4)}`;
}

function sensorShell(id: string) {
  return `<path d="M352 200Q403 178 458 177L503 190Q490 204 489 233L475 293L455 321L438 377Q403 388 315 368L310 328L304 277Q309 250 327 229Z" fill="url(#${id}-shell)" stroke="#a6b0b7" stroke-width="1"/>
    <path d="M350 269Q407 232 480 214L475 240Q414 244 354 275Z" fill="#dae0e4" opacity=".72"/>
    <path d="M354 275Q408 254 476 246L465 290L444 297L439 315L454 312L438 367L351 356Z" fill="url(#${id}-side)"/>
    <path d="M455 242l13 -5 -4 8 -11 5Zm-3 11 13 -5 -2 7 -13 5Zm-3 11 13 -5 -2 7 -13 5Zm-3 11 13 -5 -2 7 -13 5Zm-3 11 13 -5 -2 7 -13 5Z" fill="#f3f5f5"/>
    <path d="M315 367Q379 383 438 376L434 388Q375 393 315 379Z" fill="#78858f"/>
    <path d="M315 380Q374 397 433 389L426 422Q420 450 398 450L331 442Q311 435 313 412Z" fill="url(#${id}-black)"/>
    <path d="M320 387L317 419Q318 438 334 439L344 438L348 393M356 395L352 427Q351 446 370 447Q388 447 388 431L391 396M400 395L396 428Q395 443 406 441Q419 438 420 421L424 393" fill="none" stroke="#151d22" stroke-width="7"/>
    <path d="M329 391l-3 22m39 -15 -3 27m42 -27 -3 22" stroke="#5c686e" stroke-width="4"/>
    <path d="M320 266Q322 247 334 250Q346 253 348 271L350 360L321 353Z" fill="#151e24" stroke="#aebac0" stroke-width="1"/>
    <ellipse cx="334" cy="267" rx="12" ry="16" fill="url(#${id}-glass)" stroke="#9daab2" stroke-width="1.5"/><ellipse cx="334" cy="267" rx="7" ry="10" fill="#050a0d"/><ellipse cx="332" cy="262" rx="2.1" ry="2.9" fill="#d1dee2" opacity=".7"/>
    <ellipse cx="337" cy="315" rx="9" ry="11" fill="#d2d9d8"/><ellipse cx="338" cy="314" rx="6.2" ry="8" fill="url(#${id}-glass)"/><path d="M338 304l-2 4m-6 9 3 4m9 -11 -2 -3" stroke="#e8ece5" stroke-width="2"/>
    <text x="324" y="295" font-family="Arial,sans-serif" fill="#e3e9eb" font-size="4.2" font-weight="700">unitree</text>`;
}

export function dogPortrait(id: string, pose: DogPose) {
  const leg = (name: LegName, shell: (id: string) => string) =>
    `<g transform="${solveLeg(name, pose).upper}">${shell(id)}</g>${lowerLeg(id, name, pose)}`;
  return `<g transform="${portraitCamera(pose)}">
    <g fill="url(#${id}-side)">${leg("farRear", farRearShell)}${leg("farFront", farFrontShell)}</g>
    <g transform="translate(0 ${-bodyRise(pose)})">${torsoShell(id)}</g>
    ${leg("front", frontShell)}${leg("rear", rearShell)}
    <g transform="translate(0 ${-bodyRise(pose)})">${sensorShell(id)}</g>
  </g>`;
}

export function armPortrait(id: string, pose: ArmPose) {
  const shoulder = ((pose.shoulder - 1.02) * 180) / Math.PI;
  const elbow = ((pose.elbow - 1.35) * 180) / Math.PI;
  const wrist = ((pose.wrist - 0.92) * 180) / Math.PI;
  const open = pose.grip * 16;
  return `<g transform="translate(-2 76) scale(.38)">
    <path d="M825 1253L939 1222L1067 1245L1067 1257L943 1286L826 1266Z" fill="#282a2b" stroke="#666" stroke-width="2"/>
    <path d="M854 1071Q871 1048 930 1044Q1019 1050 1042 1104Q1056 1121 1053 1172L1053 1249Q995 1284 864 1258L863 1111Z" fill="url(#${id}-gunmetal)"/>
    <path d="M866 1110L866 1247Q917 1273 951 1265L952 1090" fill="url(#${id}-gunmetal)"/>
    <path d="M857 1081Q919 1107 1021 1085L1022 1100Q925 1120 854 1095Z" fill="#131516"/>
    ${screw(841, 1256, 5, 2)}${screw(1028, 1248, 5, 2)}
    <g transform="rotate(${-shoulder} 947 1010)">
      <path d="M869 943L897 914L951 889L1099 684L1136 621L1215 630L1227 673L1201 728L1036 948L1052 973L1032 1035L984 1090L895 1081L842 1046Z" fill="url(#${id}-alloy)" stroke="#a6a8a9" stroke-width="2"/>
      <path d="M950 889L1105 690L1165 684L1009 900L1018 931L987 948Q974 916 899 943L865 954L887 925Z" fill="#a0a3a5"/>
      <path d="M1009 900L1165 684L1191 698L1045 918L1018 945Z" fill="#6b6e70"/>
      <path d="M1036 877L1129 734Q1144 713 1149 726L1154 753L1067 881Q1046 905 1038 896Z" fill="#292b2c"/>
      <g transform="translate(1064 854) rotate(-55)"><text font-family="Arial,sans-serif" font-size="18" letter-spacing="1.5" fill="#c5c8c9">AGILE<tspan fill="#b73734"> X</tspan></text><text y="11" x="0" font-family="Arial,sans-serif" font-size="6" letter-spacing="3" fill="#9c9fa0">ROBOTICS</text></g>
      <path d="M1099 684L1080 655Q1063 624 1062 570L1072 533L1142 514L1218 567L1212 632L1165 684Z" fill="url(#${id}-alloy)" stroke="#999c9d" stroke-width="2"/>
      <path d="M1081 553Q1109 531 1165 541L1201 560L1200 617Q1159 646 1092 626Q1068 611 1081 553Z" fill="url(#${id}-gunmetal)"/>
      <path d="M1096 635L1134 634L1147 682L1110 681Z" fill="#5a5e60"/>
      <g transform="rotate(${-elbow} 1190 560)">
        <path d="M1217 493L1191 467L1139 441L941 295L905 300L903 336L1064 498L1053 533L1052 546L1167 541Z" fill="url(#${id}-alloy)" stroke="#a4a7a8" stroke-width="2"/>
        <path d="M929 310L1139 469L1162 514L1099 486L912 335Z" fill="#737779"/>
        <path d="M943 315L1153 472L1131 488L929 332Z" fill="#909495"/>
        <path d="M1008 358L1089 418L1079 436L1002 376Z" fill="#292c2e"/>
        <g transform="translate(1029 389) rotate(37)"><text font-family="Arial,sans-serif" font-size="16" fill="#dedfe0" font-weight="700">PiPER</text><circle cx="5" cy="-9" r="2" fill="#bc3c35"/></g>
        <g transform="rotate(${-wrist} 894 265)">
          <path d="M810 207L844 199Q909 181 933 237L949 279L943 306Q936 347 902 358Q870 367 848 331L819 335L779 222Z" fill="url(#${id}-gunmetal)" stroke="#747879" stroke-width="2"/>
          <ellipse cx="898" cy="266" rx="49" ry="70" transform="rotate(-19 898 266)" fill="#575a5c" stroke="#9b9c9d" stroke-width="2"/>
          <ellipse cx="898" cy="267" rx="37" ry="52" transform="rotate(-19 898 267)" fill="#303234"/>
          ${screw(911, 269, 4, 6)}
          <path d="M621 166Q680 136 750 118Q775 113 789 133L815 205L829 262L848 323L811 337L784 292L754 197L720 188L646 271Z" fill="url(#${id}-gunmetal)" stroke="#85898b" stroke-width="1.6"/>
          <path d="M623 166Q678 136 750 121Q770 115 780 129L753 142L639 183L622 193Q614 174 623 166Z" fill="#b7babb"/>
          <path d="M638 186L759 142L787 222L770 251L684 280L650 265Z" fill="url(#${id}-gunmetal)"/>
          <ellipse cx="779" cy="142" rx="10" ry="15" transform="rotate(-20 779 142)" fill="#171b1d" stroke="#9b9ea0" stroke-width="3"/>
          <path d="M629 176l18 -7 3 15 -19 6Z" fill="#0c1114"/><circle cx="637" cy="179" r="2.4" fill="#843d36"/>
          <path d="M663 272L721 253L774 244L788 284L763 300L733 297L704 308L674 293Z" fill="#3b3e40"/>
          ${screw(748, 266, 3.8, 5.5)}${screw(766, 256, 3.8, 5.5)}
          <path d="M672 286Q704 277 734 303L767 364Q746 389 691 412L633 410L590 355L612 327Z" fill="url(#${id}-gunmetal)" stroke="#565b5d" stroke-width="2"/>
          <path d="M693 291Q726 311 738 347L727 379L699 395L692 370L679 342L654 318" fill="#494d4f"/>
          <path d="M708 318Q726 335 730 351L726 368" fill="none" stroke="#111618" stroke-width="4"/>
          ${screw(691, 307, 5.5, 4)}${screw(752, 329, 3, 5)}
          <path d="M557 313Q574 301 589 307L601 332L586 351L563 336Z" fill="#595d60" stroke="#9fa4a6" stroke-width="2"/>
          ${screw(578, 317, 3, 3)}
          <path d="M594 335L687 370L699 399L636 443L578 470L518 437L522 377Z" fill="url(#${id}-gunmetal)" stroke="#666c70" stroke-width="2"/>
          <path d="M608 367L673 386L680 405L632 426L613 403Z" fill="#747a7d"/>
          ${screw(659, 394, 3, 3.5)}${screw(633, 399, 3, 4)}
          <g transform="translate(0 ${-open})"><path d="M570 345Q589 343 600 362L623 420L625 449Q600 470 556 470L455 495L438 452L484 408L504 362L533 350Z" fill="url(#${id}-alloy)" stroke="#a1a6a9" stroke-width="2"/>
          <path d="M573 358Q586 358 590 376L609 424L609 443L570 459L472 480L460 447L513 401Z" fill="#3a3e41"/>
          <path d="M566 389L587 385L603 434L581 448L499 474L480 447Z" fill="url(#${id}-gunmetal)"/>
          <path d="M442 451L458 491L469 490L455 449L524 388L566 350L541 355L497 400Z" fill="#6d7377"/>
          <path d="M475 396L493 386L497 401L480 412Z" fill="#545b5f"/></g>
          <path d="M589 ${369 + open}L613 ${401 + open}L621 ${439 + open}L606 ${444 + open}L590 ${408 + open}L566 ${392 + open}" fill="#272e31" stroke="#717b81" stroke-width="3"/>
        </g>
      </g>
      <path d="M1180 518Q1215 486 1241 518Q1264 547 1263 594L1228 642L1212 655L1198 632L1181 581Z" fill="url(#${id}-alloy)" stroke="#a6aaab" stroke-width="2"/>
      <ellipse cx="1223" cy="562" rx="37" ry="59" transform="rotate(-12 1223 562)" fill="url(#${id}-joint)" stroke="#141719" stroke-width="5"/>
      <ellipse cx="1228" cy="562" rx="24" ry="44" transform="rotate(-12 1228 562)" fill="#2b2e30"/>
      <ellipse cx="1230" cy="562" rx="11" ry="19" transform="rotate(-12 1230 562)" fill="none" stroke="#b23433" stroke-width="2"/>
      <text x="1245" y="543" font-size="7" fill="#a6aaaa" transform="rotate(68 1245 543)" font-family="Arial,sans-serif">AGILE X</text>
      <path d="M864 946Q906 932 966 953L1000 979L1005 1046L977 1084L910 1092L850 1070Q825 1040 831 1000Q835 963 864 946Z" fill="url(#${id}-gunmetal)" stroke="#7c8184" stroke-width="3"/>
      <path d="M853 958Q832 1000 842 1035L858 1053M949 956Q928 1003 941 1059" fill="none" stroke="#151a1d" stroke-width="5"/>
      <ellipse cx="997" cy="1019" rx="48" ry="65" transform="rotate(16 997 1019)" fill="url(#${id}-joint)" stroke="#7c8184" stroke-width="4"/>
      <ellipse cx="1001" cy="1021" rx="32" ry="46" transform="rotate(16 1001 1021)" fill="#303335"/>
      <ellipse cx="1005" cy="1020" rx="15" ry="23" transform="rotate(16 1005 1020)" stroke="#b73332" stroke-width="2.5" fill="none"/>
      <text x="1007" y="995" font-family="Arial,sans-serif" font-size="7" fill="#b6b9ba" transform="rotate(22 1007 995)">AGILE X</text>
      ${screw(875, 958, 5, 3)}${screw(862, 1044, 5, 4)}${screw(970, 1084, 3, 5)}
    </g>
  </g>`;
}
