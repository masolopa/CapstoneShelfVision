
import './RegovaLogo.css';

type RegovaLogoProps = {
  size?: number;
};

function RegovaLogo({ size = 76 }: RegovaLogoProps) {
  return (
    <svg
      className="regova-logo"
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M10 15 H22 L33 62 H75 L86 29 H26"
        stroke="currentColor"
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      <circle cx="38" cy="78" r="6" fill="currentColor" />
      <circle cx="72" cy="78" r="6" fill="currentColor" />
    </svg>
  );
}

export default RegovaLogo;
