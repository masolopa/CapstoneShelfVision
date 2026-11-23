
interface ImageUploadIconProps {
  size?: number;
  className?: string;
}

function ImageUploadIcon({
  size = 56,
  className,
}: ImageUploadIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect
        x="9"
        y="9"
        width="46"
        height="46"
        rx="5"
        stroke="#153D70"
        strokeWidth="2.8"
      />

      <circle
        cx="43"
        cy="23"
        r="5"
        fill="#45B7FF"
      />

      <path
        d="M12 47L26 30L36 40L42 34L52 47"
        stroke="#153D70"
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default ImageUploadIcon;
