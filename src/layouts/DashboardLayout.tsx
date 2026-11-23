
import type { ReactNode } from 'react';

import Sidebar from '../components/Sidebar/Sidebar';
import type { SidebarSection } from '../components/Sidebar/Sidebar';
import type { User } from '../services/auth';

import Header from '../components/Header/Header';

import './DashboardLayout.css';

interface DashboardLayoutProps {
  activeSection: SidebarSection;
  onNavigate: (section: SidebarSection) => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  currentUser: User;
  onLogout: () => void;
}

export default function DashboardLayout({
  activeSection,
  onNavigate,
  title,
  subtitle,
  children,
  currentUser,
  onLogout,
}: DashboardLayoutProps) {
  return (
    <div className="dashboard-layout">
      <Sidebar
        activeSection={activeSection}
        onNavigate={onNavigate}
        currentUser={currentUser}
        onLogout={onLogout}
      />

      <div className="dashboard-layout-workspace">
        <Header
          title={title}
          subtitle={subtitle}
          username={currentUser.name}
          role={currentUser.role}
        />

        <main className="dashboard-layout-content">
          {children}
        </main>
      </div>
    </div>
  );
}
