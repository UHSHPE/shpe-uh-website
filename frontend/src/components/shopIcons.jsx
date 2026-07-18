// Inline SVG icons from the shop design handoff (stroke 1.8, round caps).

function Svg({ size = 18, stroke = "currentColor", strokeWidth = 1.8, children, style }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
    >
      {children}
    </svg>
  );
}

export function CartIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="20" r="1.3" />
      <circle cx="18" cy="20" r="1.3" />
      <path d="M2 3h2.3l2 12.2a1.6 1.6 0 0 0 1.6 1.3h8.8a1.6 1.6 0 0 0 1.6-1.3L20.2 7H5.3" />
    </Svg>
  );
}

export function BoxIcon(props) {
  return (
    <Svg {...props}>
      <path d="M3 7l9-4 9 4-9 4-9-4z" />
      <path d="M3 7v10l9 4 9-4V7" />
    </Svg>
  );
}

export function CheckIcon(props) {
  return (
    <Svg strokeWidth={2.4} {...props}>
      <path d="M5 13l4 4L19 7" />
    </Svg>
  );
}

export function TrashIcon(props) {
  return (
    <Svg {...props}>
      <path d="M4 7h16M9 7V5h6v2M6 7l1 13h10l1-13" />
    </Svg>
  );
}

export function PencilIcon(props) {
  return (
    <Svg {...props}>
      <path d="M4 20h4L18 10l-4-4L4 16v4z" />
      <path d="M14 6l4 4" />
    </Svg>
  );
}

export function CloseIcon(props) {
  return (
    <Svg strokeWidth={2} {...props}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  );
}

export function MinusIcon(props) {
  return (
    <Svg strokeWidth={2.4} {...props}>
      <path d="M5 12h14" />
    </Svg>
  );
}

export function PlusIcon(props) {
  return (
    <Svg strokeWidth={2.4} {...props}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function BackIcon(props) {
  return (
    <Svg strokeWidth={2} {...props}>
      <path d="M15 19l-7-7 7-7" />
    </Svg>
  );
}

export function ChevronDownIcon(props) {
  return (
    <Svg strokeWidth={2} {...props}>
      <path d="M6 9l6 6 6-6" />
    </Svg>
  );
}

export function CardIcon(props) {
  return (
    <Svg strokeWidth={1.9} {...props}>
      <rect x="3" y="6" width="18" height="12" rx="2" />
      <path d="M3 10h18" />
    </Svg>
  );
}

export function ImageIcon(props) {
  return (
    <Svg strokeWidth={1.7} {...props}>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <circle cx="9" cy="9" r="2" />
      <path d="M21 15l-5-5L5 21" />
    </Svg>
  );
}
