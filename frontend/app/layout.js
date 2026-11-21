import Providers from './providers';
import './globals.css';

export const metadata = {
  title: 'Sybil-Net Marketplace',
  description: 'Trust-verified DeFi marketplace powered by Graph Neural Network Sybil detection. Three pillars: Zero Wash-Trading Exchange, Undercollateralised Credit Hub, Sybil-Resistant Yield Hub.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
