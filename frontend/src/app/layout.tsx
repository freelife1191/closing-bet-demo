import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KR Market Dashboard",
  description: "Korean Stock Market Analysis System",
};

import ChatWidget from "./components/ChatWidget";
import Providers from "./components/Providers";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link
          rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"
        />
      </head>
      <body>
        <Providers>
          {children}
          <ChatWidget />
        </Providers>
      </body>
    </html>
  );
}
