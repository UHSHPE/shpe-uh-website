import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import shpeSpirit from "../assets/images/SHPESpiritWeb.jpg"
import shpeLogo from "../assets/images/shpelogo.png"
import homeDecor from "../assets/images/homeDecor.png"
import waves from "../assets/images/waves.png"
import polygons from "../assets/images/Deco.png"

import { useAuth } from '../context/AuthContext'
import useDocumentTitle from "../hooks/useDocumentTitle"

export default function Home() {
	useDocumentTitle()
	const [email, setEmail] = useState('');
	const [instaPosts, setInstaPosts] = useState([]);
	const navigate = useNavigate();
	const { user } = useAuth()

	const handleMainButtonClick = () => user ? navigate('/dashboard') : navigate('/signup')

	// Fetch the public Behold Instagram feed (external CDN — uses fetch, not api.js).
	// On any error we leave instaPosts empty so the shimmer placeholder stays as fallback.
	useEffect(() => {
		const feedUrl = import.meta.env.VITE_BEHOLD_FEED_URL;
		if (!feedUrl) return;
		let active = true;
		fetch(feedUrl)
			.then((res) => {
				if (!res.ok) throw new Error(`Behold feed responded ${res.status}`);
				return res.json();
			})
			.then((data) => {
				if (active) setInstaPosts((data.posts || []).slice(0, 6));
			})
			.catch(() => {
				if (active) setInstaPosts([]);
			});
		return () => { active = false; };
	}, []);
	
	return (
		<section className="text-[#001F5B] overflow-x-hidden">
			<section className="relative min-h-[480px] sm:min-h-[90vh] w-full overflow-hidden">

				{/* Image and pattern section */}
				<div className='absolute h-full w-[80%] hidden md:block'>
					{/* Image and Shadow Section */}
					<div className='shadowWrapper absolute z-80 w-full h-full' style={{ filter: "drop-shadow(6px 12px 20px rgba(0,0,0,0.8))"}}>
						<div
						className="imageClip absolute left-0 top-0 h-full w-full overflow-hidden"
						style={{
							clipPath: "polygon(0 0, clamp(10%, 15vw, 20%) 0, clamp(55%, 65vw, 75%) 100%, 0 100%)",
						}}
						>							
						<img
							src={shpeSpirit}
							alt="SHPE members"
							className="absolute h-full w-full object-cover object-[95%_center]"
							/>
						</div>
					</div>

					{/* Deco Image */}
					<img
						src={polygons}
						alt="Polygon decoration"
						className="absolute top-0 z-10 h-full object-contain"
						style={{
							width: "min(68vw, 986px)",
							right: "clamp(1%, 14vw, 20%)",
							objectPosition: "top",
						}}
					/>
				</div>

				{/* Right: headline + CTA */}
				<div className="absolute inset-y-0 right-0 z-100 w-full px-6 md:w-[40%] md:px-0 flex flex-col items-center justify-center gap-10 md:justify-evenly md:gap-0">
					<p className="font-semibold text-[clamp(1.75rem,8vw,3.5rem)] leading-tight tracking-tight text-center">
						<span className="text-[#D33A02]">Join</span> the{' '}
						<span className="text-[#FD652F]">leading</span>
						<br />
						<span className="text-[#0070C0]">Familia</span> in{' '}
						<span className="text-[#72A9BE]">STEM</span>
					</p>

					<p className="text-center font-semibold text-[clamp(1.35rem,6vw,3rem)] leading-snug tracking-tight [text-shadow:0_4px_4px_#fff] text-[#001F5B]">
						Your journey<br/>starts at SHPE
						<br />
						<span className="text-[#C8102E]">University of<br/>Houston</span>
					</p>

					<button
						type="button"
						className="text-white text-xl font-bold p-4 bg-[#D24028] border border-[#7e2704] rounded-[20px] hover:opacity-75 cursor-pointer"
						onClick={handleMainButtonClick}
					>
						{ user ? "Go to Dashboard" : "Become Member"}
					</button>
				</div>
			</section>
			
			<section
				id="info"
				className="bg-white md:py-20 py-5 px-10 flex flex-row w-screen items-center justify-evenly flex-wrap gap-20"
			>
				<div className="flex flex-col md:items-end flex-1 w-[75%] md:text-right">
					<h2 className="text-[#D33A02] font-semibold text-3xl mb-3">
						What we do?
					</h2>
					<p className="lg:w-[60%] text-lg text-[#001F5B]">
						The Society of Hispanic Professional Engineers (SHPE){' '}
						<span className="text-[#C8102E]">University of Houston</span>{' '}
						chapter was founded in 2002. Since then this chapter has been
						dedicated to promote the professional, leadership, and academic
						development of our members and encourage awareness in Science and
						Engineering studies among the Hispanic community. Through a series
						of general meetings, events, workshops, and conferences, the SHPE-UH
						chapter aims to provide opportunities that will propel our members
						to succeed in the professional world and beyond!
					</p>
				</div>

				<div className="flex-1 items-center justify-center hidden md:block">
					<img
						src={shpeLogo}
						alt="SHPE logo"
						className="md:w-[80%] lg:w-[50%] mix-blend-multiply"
					/>
				</div>
			</section>

			<section
				id="insta"
				className="relative bg-white px-[8%] py-16"
			>
				{/* homeDecor.png — floating circles background */}
				<div className="absolute inset-0 z-0 pointer-events-none">
					<img
						src={homeDecor}
						alt=""
						aria-hidden="true"
						className="w-full h-full object-cover mix-blend-screen opacity-85"
					/>
				</div>

				<h2 className="relative z-[1] text-center italic font-semibold text-[clamp(1.2rem,2.5vw,1.8rem)] mb-6 text-[#001F5B]">
					Follow us on Instagram:{' '}
					<a
						href="https://www.instagram.com/shpe_uh/"
						target="_blank"
						rel="noopener noreferrer"
						className="text-[#0070C0] hover:underline"
					>
						@shpe_uh
					</a>
				</h2>

				{/* 3×2 grid — real posts from the Behold feed; shimmer placeholder is the fallback */}
				<div className="relative z-[1] grid grid-cols-3 gap-1 max-w-[520px] mx-auto rounded-lg overflow-hidden shadow-[0_4px_30px_rgba(0,31,91,0.15)]">
					{instaPosts.length > 0 ? (
						instaPosts.map((post) => (
							<a
								key={post.id}
								href={post.permalink}
								target="_blank"
								rel="noopener noreferrer"
								className="aspect-square bg-[#dde6f0] overflow-hidden block"
							>
								<img
									src={post.sizes?.medium?.mediaUrl || post.mediaUrl}
									alt={post.prunedCaption || 'SHPE UH Instagram post'}
									loading="lazy"
									className="w-full h-full object-cover"
								/>
							</a>
						))
					) : (
						Array.from({ length: 6 }).map((_, i) => (
							<div key={i} className="aspect-square bg-[#dde6f0] overflow-hidden">
								<div className="w-full h-full bg-gradient-to-br from-[#e0e9f3] via-[#c5d3e6] to-[#e0e9f3] animate-pulse" />
							</div>
						))
					)}
				</div>
			</section>

			<section
				id="newsletter"
				className="relative md:min-h-[400px] bg-[#001F5B] overflow-hidden flex flex-col items-center justify-center md:py-0 py-25 px-4 text-center"
			>
				{/* waves.png background */}
				<div className="absolute inset-0 z-0 pointer-events-none">
					<img
						src={waves}
						alt=""
						aria-hidden="true"
						className="w-full h-full object-cover"
					/>
				</div>

				<h2 className="relative z-1 text-white font-semibold text-[clamp(1.8rem,4vw,2.5rem)] sm:mb-2 mb-0">
					NEWSLETTER INTEREST FORM
				</h2>

				<p className="relative z-1 text-[#F16635] font-semibold text-base mb-8">
					Sign up for news and opportunities
				</p>

				<form
					className="relative z-1 flex flex-row gap-5 flex-wrap justify-center"
					onSubmit={(e) => {
						e.preventDefault();
						alert(`Subscribed: ${email}`);
						setEmail('');
					}}
				>
					<input
						type="email"
						placeholder="Enter your email"
						value={email}
						onChange={(e) => setEmail(e.target.value)}
						required
						className="w-[clamp(200px,35vw,360px)] h-13.5 bg-white rounded-[20px] px-5 text-[#001F5B] text-base outline-none focus:ring-2 focus:ring-[#0070C0]"
					/>
					<button
						type="submit"
						className="text-white font-bold h-13.5 px-5 bg-[#D24028] rounded-[20px]"
						>
						Subscribe
					</button>
				</form>
			</section>
		</section>
	);
}
