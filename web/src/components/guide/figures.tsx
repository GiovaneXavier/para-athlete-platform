import type { ReactNode } from "react";
import { formatDecimal, formatInteger } from "@/lib/guide";
import type { Figure } from "@/lib/guide-types";
import { Rich } from "./rich";

/*
 * Original schemes drawn from the same data as the text. Monochrome on purpose: only currentColor
 * (the text colour), so contrast follows the theme and nothing is conveyed by colour. Bands and limbs are
 * told apart by pattern and by a written label. Text is at least 13 units in a 320-unit-wide drawing.
 */

const FONT = 13;
type Point = [number, number];

function Patterns({ prefix }: { prefix: string }) {
  return (
    <defs>
      <pattern id={`${prefix}-dots`} width="7" height="7" patternUnits="userSpaceOnUse">
        <circle cx="3.5" cy="3.5" r="1.4" fill="currentColor" />
      </pattern>
      <pattern id={`${prefix}-cross`} width="7" height="7" patternUnits="userSpaceOnUse">
        <path d="M0,0 L7,7 M0,7 L7,0" stroke="currentColor" strokeWidth="1" />
      </pattern>
      <pattern id={`${prefix}-diagonal`} width="7" height="7" patternUnits="userSpaceOnUse">
        <path d="M0,7 L7,0" stroke="currentColor" strokeWidth="1.6" />
      </pattern>
      <pattern id={`${prefix}-vertical`} width="6" height="6" patternUnits="userSpaceOnUse">
        <path d="M3,0 L3,6" stroke="currentColor" strokeWidth="2.2" />
      </pattern>
    </defs>
  );
}

function Svg({ figure, height, children }: { figure: Figure; height: number; children: ReactNode }) {
  const titleId = `${figure.id}-title`;
  const descId = `${figure.id}-desc`;
  return (
    <svg
      viewBox={`0 0 320 ${height}`}
      role="img"
      aria-labelledby={titleId}
      aria-describedby={descId}
      className="h-auto w-full max-w-md text-foreground"
      fontSize={FONT}
      fill="none"
      stroke="currentColor"
    >
      <title id={titleId}>{figure.title}</title>
      <desc id={descId}>{figure.long}</desc>
      <Patterns prefix={figure.id} />
      {children}
    </svg>
  );
}

function Label({ x, y, anchor = "start", children }: { x: number; y: number; anchor?: "start" | "end" | "middle"; children: ReactNode }) {
  return (
    <text x={x} y={y} textAnchor={anchor} fill="currentColor" stroke="none" fontSize={FONT}>
      {children}
    </text>
  );
}

// --- logMAR scale -------------------------------------------------------------------------------------------

function LogmarScale({ figure }: { figure: Extract<Figure, { kind: "logmar_scale" }> }) {
  const { axis, bands } = figure.data;
  const left = 20;
  const width = 280;
  const x = (value: number) => left + ((value - axis.min) / (axis.max - axis.min)) * width;
  return (
    <Svg figure={figure} height={56 + bands.length * 44}>
      <line x1={left} x2={left + width} y1={34} y2={34} strokeWidth={1.5} />
      {axis.ticks.map((tick) => (
        <g key={tick}>
          <line x1={x(tick)} x2={x(tick)} y1={28} y2={40} strokeWidth={1.5} />
          <Label x={x(tick)} y={22} anchor="middle">
            {formatInteger(tick)}
          </Label>
        </g>
      ))}
      {bands.map((band, index) => {
        const y = 52 + index * 44;
        const above = band.to >= axis.max;
        const start = x(band.from);
        const end = x(band.to);
        const range = above
          ? `acima de ${formatDecimal(band.from)}`
          : `de ${formatDecimal(band.from)} a ${formatDecimal(band.to)}`;
        const onLeft = end > 200;
        const lx = onLeft ? start - 6 : end + 6;
        const anchor = onLeft ? "end" : "start";
        return (
          <g key={band.label}>
            <rect x={start} y={y} width={end - start} height={22} fill={`url(#${figure.id}-${band.pattern})`} strokeWidth={1.5} />
            <Label x={lx} y={y + 10} anchor={anchor}>
              {band.label}
            </Label>
            <Label x={lx} y={y + 25} anchor={anchor}>
              {range}
            </Label>
          </g>
        );
      })}
    </Svg>
  );
}

// --- visual field ---------------------------------------------------------------------------------------------

function FieldCircles({ figure }: { figure: Extract<Figure, { kind: "field_circles" }> }) {
  const [small, large] = figure.data.limits;
  const cx = 105;
  const cy = 105;
  const outer = 92;
  const inner = (outer * small) / large;
  const [label12, label13] = figure.data.labels;
  return (
    <Svg figure={figure} height={215}>
      <circle cx={cx} cy={cy} r={outer} fill={`url(#${figure.id}-dots)`} strokeWidth={1.5} />
      <circle cx={cx} cy={cy} r={inner} fill={`url(#${figure.id}-diagonal)`} strokeWidth={1.5} />
      <line x1={cx + outer * 0.7} y1={cy - outer * 0.7} x2={208} y2={52} strokeWidth={1} />
      <Label x={212} y={50}>
        {label13}
      </Label>
      <Label x={212} y={68}>
        {`de ${formatInteger(small)} a ${formatInteger(large)}`}
      </Label>
      <Label x={212} y={86}>
        graus de diâmetro
      </Label>
      <line x1={cx + inner * 0.7} y1={cy + inner * 0.7} x2={208} y2={148} strokeWidth={1} />
      <Label x={212} y={146}>
        {label12}
      </Label>
      <Label x={212} y={164}>
        {`abaixo de ${formatInteger(small)}`}
      </Label>
      <Label x={212} y={182}>
        graus de diâmetro
      </Label>
    </Svg>
  );
}

// --- stick figure ---------------------------------------------------------------------------------------------

const ARM: Record<"left" | "right", Point[]> = {
  left: [
    [160, 64],
    [125, 98],
    [103, 128],
    [95, 146],
  ],
  right: [
    [160, 64],
    [195, 98],
    [217, 128],
    [225, 146],
  ],
};
const LEG: Record<"left" | "right", Point[]> = {
  left: [
    [160, 130],
    [138, 184],
    [133, 230],
    [113, 240],
  ],
  right: [
    [160, 130],
    [182, 184],
    [187, 230],
    [207, 240],
  ],
};

const lerp = (a: Point, b: Point, t: number): Point => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
const path = (points: Point[]) => points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0]},${p[1]}`).join(" ");

/** Cut point of a limb for an amputation level, and the points drawn up to it. */
function cutLimb(points: Point[], kind: "lower" | "upper", level: number): { drawn: Point[]; cut: Point | null } {
  if (level === 0) return { drawn: points, cut: null };
  let cut: Point;
  let keep: number;
  if (kind === "lower") {
    if (level === 1) [cut, keep] = [lerp(points[2], points[3], 0.5), 3];
    else if (level === 2) [cut, keep] = [lerp(points[1], points[2], 0.5), 2];
    else [cut, keep] = [lerp(points[0], points[1], 0.55), 1];
  } else if (level === 1) [cut, keep] = [points[2], 3];
  else [cut, keep] = [points[1], 2];
  return { drawn: [...points.slice(0, keep), cut], cut };
}

function Body() {
  return (
    <g strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
      <circle cx={160} cy={30} r={14} />
      <line x1={160} y1={44} x2={160} y2={130} />
    </g>
  );
}

function PatternFigure({ figure }: { figure: Extract<Figure, { kind: "pattern" }> }) {
  const { levels, labels, prosthesis, show_upper } = figure.data;
  const limbs: { key: keyof typeof levels; side: "left" | "right"; kind: "lower" | "upper"; points: Point[] }[] = [
    { key: "lower_left", side: "left", kind: "lower", points: LEG.left },
    { key: "lower_right", side: "right", kind: "lower", points: LEG.right },
    ...(show_upper
      ? [
          { key: "upper_left" as const, side: "left" as const, kind: "upper" as const, points: ARM.left },
          { key: "upper_right" as const, side: "right" as const, kind: "upper" as const, points: ARM.right },
        ]
      : []),
  ];
  return (
    <Svg figure={figure} height={prosthesis ? 275 : 255}>
      <Body />
      {!show_upper
        ? [ARM.left, ARM.right].map((points, index) => (
            <path key={index} d={path(points)} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
          ))
        : null}
      {limbs.map((limb) => {
        const level = levels[limb.key];
        const { drawn, cut } = cutLimb(limb.points, limb.kind, level);
        const label = labels[limb.key];
        return (
          <g key={limb.key}>
            <path d={path(drawn)} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
            {cut ? (
              <>
                <line x1={cut[0] - 7} y1={cut[1]} x2={cut[0] + 7} y2={cut[1]} strokeWidth={4} strokeLinecap="round" />
                {prosthesis && limb.kind === "lower" ? (
                  <path d={path([cut, limb.points[limb.points.length - 1]])} strokeWidth={2.5} strokeDasharray="5 5" />
                ) : null}
                {label ? (
                  <Label x={limb.side === "left" ? cut[0] - 14 : cut[0] + 14} y={cut[1] + 4} anchor={limb.side === "left" ? "end" : "start"}>
                    {label}
                  </Label>
                ) : null}
              </>
            ) : null}
          </g>
        );
      })}
      {prosthesis ? <Label x={8} y={268}>Linha tracejada: prótese de corrida</Label> : null}
    </Svg>
  );
}

function StatureFigure({ figure }: { figure: Extract<Figure, { kind: "stature_measures" }> }) {
  const { height, arm } = figure.data.labels;
  return (
    <Svg figure={figure} height={282}>
      <Body />
      <path d={path(ARM.right)} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
      <path d={path(ARM.left)} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" strokeDasharray="7 5" />
      {[LEG.left, LEG.right].map((points, index) => (
        <path key={index} d={path(points)} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
      ))}
      <line x1={104} y1={128} x2={64} y2={170} strokeWidth={1.5} />
      <Label x={6} y={188}>
        {arm}
      </Label>
      <line x1={262} y1={14} x2={262} y2={242} strokeWidth={2} />
      <line x1={254} y1={14} x2={270} y2={14} strokeWidth={2} />
      <line x1={254} y1={242} x2={270} y2={242} strokeWidth={2} />
      <Label x={262} y={264} anchor="middle">
        {height}
      </Label>
    </Svg>
  );
}

function LevelsFigure({ figure }: { figure: Extract<Figure, { kind: "levels_lower" | "levels_upper" }> }) {
  const lower = figure.kind === "levels_lower";
  const points: Point[] = lower
    ? [
        [110, 20],
        [100, 100],
        [95, 185],
        [72, 200],
      ]
    : [
        [110, 20],
        [88, 100],
        [70, 175],
        [64, 200],
      ];
  const dash: Record<string, string | undefined> = lower ? { "1": "2 4", "2": "7 5", "3": undefined } : { "1": "7 5", "2": undefined };
  const markAt = (level: number): Point =>
    lower
      ? level === 1
        ? lerp(points[2], points[3], 0.5)
        : level === 2
          ? lerp(points[1], points[2], 0.5)
          : lerp(points[0], points[1], 0.55)
      : level === 1
        ? points[2]
        : points[1];
  return (
    <Svg figure={figure} height={225}>
      <path d={path(points)} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" />
      {figure.data.marks.map((mark) => {
        const [mx, my] = markAt(mark.level);
        return (
          <g key={mark.level}>
            <line x1={mx - 22} x2={178} y1={my} y2={my} strokeWidth={2} strokeDasharray={dash[String(mark.level)]} />
            <Label x={184} y={my + 4}>
              {mark.label}
            </Label>
          </g>
        );
      })}
    </Svg>
  );
}

export function FigureView({ figure }: { figure: Figure }) {
  let drawing: ReactNode;
  switch (figure.kind) {
    case "logmar_scale":
      drawing = <LogmarScale figure={figure} />;
      break;
    case "field_circles":
      drawing = <FieldCircles figure={figure} />;
      break;
    case "stature_measures":
      drawing = <StatureFigure figure={figure} />;
      break;
    case "levels_lower":
    case "levels_upper":
      drawing = <LevelsFigure figure={figure} />;
      break;
    case "pattern":
      drawing = <PatternFigure figure={figure} />;
      break;
  }
  return (
    <figure className="max-w-md space-y-2">
      {drawing}
      <figcaption className="text-sm text-foreground/85">
        <Rich segments={figure.caption} />
      </figcaption>
      <details className="text-sm">
        <summary className="cursor-pointer rounded-sm font-medium focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50">
          Descrição da figura
        </summary>
        <p className="mt-1 leading-relaxed">{figure.long}</p>
      </details>
    </figure>
  );
}
