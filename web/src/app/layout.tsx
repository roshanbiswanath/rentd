import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Space_Grotesk } from "next/font/google";
import "./globals.css";

const plusJakartaSans = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
});

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space-grotesk",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Rentd | Curated Urban Rentals",
  description:
    "Find high-signal rental listings curated from social channels, presented in a clean and thoughtful search experience.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="light">
      <body
        className={`${plusJakartaSans.variable} ${spaceGrotesk.variable} bg-app antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
