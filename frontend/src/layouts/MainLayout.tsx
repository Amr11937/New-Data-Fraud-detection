import { NavLink, Outlet } from 'react-router-dom';
import {
  AppBar,
  Box,
  Button,
  Chip,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import DashboardIcon from '@mui/icons-material/Dashboard';
import PeopleIcon from '@mui/icons-material/People';
import InsightsIcon from '@mui/icons-material/Insights';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import LockResetIcon from '@mui/icons-material/LockReset';
import PersonIcon from '@mui/icons-material/Person';
import LogoutIcon from '@mui/icons-material/Logout';
import { useAuth } from '@/auth/AuthContext';
import logoMark from '@/assets/logo-mark.png';
import { useWebSocket } from '@/hooks/useWebSocket';
import { AlertBanner } from '@/components/AlertBanner';

const DRAWER_WIDTH = 220;

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Executive summary', icon: <DashboardIcon />, end: true },
  { to: '/dashboard/subscribers', label: 'Subscribers', icon: <PeopleIcon /> },
  { to: '/dashboard/risk', label: 'Risk analytics', icon: <InsightsIcon /> },
  { to: '/dashboard/health', label: 'System health', icon: <MonitorHeartIcon /> },
  { to: '/dashboard/demask', label: 'Demask', icon: <LockResetIcon /> },
];

export default function MainLayout() {
  const { isConnected } = useWebSocket();
  const { user, logout } = useAuth();

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar sx={{ gap: 2 }}>
          <Box
            component="img"
            src={logoMark}
            alt="FraudVision AI logo"
            sx={{ height: 50, width: 'auto', display: 'block' }}
          />
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 700 }}>
            FraudVision AI
          </Typography>
          <Chip
            label={isConnected ? 'Live' : 'Reconnecting…'}
            color={isConnected ? 'success' : 'default'}
            size="small"
            variant="outlined"
          />
          <Chip icon={<PersonIcon />} label={user} size="small" variant="outlined" />
          <Button color="inherit" size="small" startIcon={<LogoutIcon />} onClick={logout}>
            Sign out
          </Button>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: DRAWER_WIDTH, boxSizing: 'border-box' },
        }}
      >
        <Toolbar />
        <List>
          {NAV_ITEMS.map((item) => (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              end={item.end}
              sx={{ '&.active': { bgcolor: 'action.selected' } }}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3, width: `calc(100% - ${DRAWER_WIDTH}px)` }}>
        <Toolbar />
        <AlertBanner />
        <Outlet />
      </Box>
    </Box>
  );
}
