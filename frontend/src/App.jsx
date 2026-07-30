import { Routes, Route, Navigate } from 'react-router-dom';
import Header from './components/Header';
import Footer from './components/Footer';
import PrivateRoute from './components/PrivateRoute';

import Home from './pages/home';
import About from './pages/about';
import GetInvolved from './pages/get-involved';
import MemberSHPE from './pages/membershpe';
import Sponsors from './pages/sponsors';
import Gallery from './pages/gallery';
import SignIn from './pages/signin';
import SignUp from './pages/signup';
import ForgotPassword from './pages/forgot-password';
import ResetPassword from './pages/reset-password';
import Dashboard from './pages/dashboard';
import Committees from './pages/committees';
import Calendar from './pages/calendar';
import Profile from './pages/profile';
import Members from './pages/members';
import ShopManagerPage from './pages/shop-manager';
import Shop from './pages/shop';
import ShopProduct from './pages/shop-product';
import ShopCheckout from './pages/shop-checkout';
import ShopOrder from './pages/shop-order';
import CartDrawer, { ShopToast } from './components/CartDrawer';
import DuesBanner from './components/DuesBanner';

export default function App() {
	return (
		<div className="app">
			<Header />
			<DuesBanner />
			<main className="main">
				<Routes>
					<Route path="/" element={<Home />} />
					<Route path="/about" element={<About />} />
					{/* <Route path="/get-involved" element={<GetInvolved />} /> */}
					<Route path="/membershpe" element={<MemberSHPE />} />
					<Route path="/sponsors" element={<Sponsors />} />
					<Route path="/gallery" element={<Gallery />} />
					<Route path="/calendar" element={<Calendar />} />
					<Route path="/shop" element={<Shop />} />
					<Route path="/shop/checkout" element={<ShopCheckout />} />
					<Route path="/shop/order/:code" element={<ShopOrder />} />
					<Route path="/shop/:productId" element={<ShopProduct />} />
					<Route path="/signin" element={<SignIn />} />
					<Route path="/signup" element={<SignUp />} />
					<Route path="/forgot-password" element={<ForgotPassword />} />
					<Route path="/reset-password" element={<ResetPassword />} />
					<Route
						path="/dashboard"
						element={
							<PrivateRoute>
								<Dashboard />
							</PrivateRoute>
						}
					/>
					<Route
						path="/committees"
						element={
							<PrivateRoute>
								<Committees />
							</PrivateRoute>
						}
					/>
					<Route
						path="/profile"
						element={
							<PrivateRoute>
								<Profile />
							</PrivateRoute>
						}
					/>
					<Route
						path="/members"
						element={
							<PrivateRoute>
								<Members />
							</PrivateRoute>
						}
					/>
					<Route
						path="/shop-manager"
						element={
							<PrivateRoute>
								<ShopManagerPage />
							</PrivateRoute>
						}
					/>
					{/* Redirect old /pages/ routes */}
					<Route
						path="/pages/about"
						element={<Navigate to="/about" replace />}
					/>
					{/* <Route
						path="/pages/get-involved"
						element={<Navigate to="/get-involved" replace />}
					/> */}
					<Route
						path="/pages/membershpe"
						element={<Navigate to="/membershpe" replace />}
					/>
					<Route
						path="/pages/sponsors"
						element={<Navigate to="/sponsors" replace />}
					/>
					<Route
						path="/pages/gallery"
						element={<Navigate to="/gallery" replace />}
					/>
				</Routes>
			</main>
			<Footer />
			{/* Global shop overlays — the cart drawer can open from any route */}
			<CartDrawer />
			<ShopToast />
		</div>
	);
}
