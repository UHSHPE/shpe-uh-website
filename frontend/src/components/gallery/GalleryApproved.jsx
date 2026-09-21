import { useEffect, useMemo, useState } from "react";

import { galleryPhotoImageUrl, getGalleryPhotos } from "../../api/api";
import springImg1 from "../../assets/images/Spring2026/img1.JPG";
import springImg2 from "../../assets/images/Spring2026/img2.JPG";
import springImg3 from "../../assets/images/Spring2026/img3.JPG";
import springImg4 from "../../assets/images/Spring2026/img4.JPG";
import springImg5 from "../../assets/images/Spring2026/img5.JPG";
import springImg6 from "../../assets/images/Spring2026/img6.JPG";
import springImg7 from "../../assets/images/Spring2026/img7.JPG";
import springImg8 from "../../assets/images/Spring2026/img8.JPG";

import fallImg1 from "../../assets/images/Fall2025/img1.JPG";
import fallImg2 from "../../assets/images/Fall2025/img2.JPG";
import fallImg3 from "../../assets/images/Fall2025/img3.JPG";
import fallImg4 from "../../assets/images/Fall2025/img4.JPG";
import fallImg5 from "../../assets/images/Fall2025/img5.JPG";
import fallImg6 from "../../assets/images/Fall2025/img6.JPG";
import fallImg7 from "../../assets/images/Fall2025/img7.JPG";
import fallImg8 from "../../assets/images/Fall2025/img8.JPG";
import { gallerySectionTitle } from "../../utils/gallery";
import GalleryUpload from "./GalleryUpload";

const imageLayoutClasses = [
  "col-span-12 h-48 sm:col-span-4 sm:h-[284px]",
  "col-span-6 h-36 sm:col-span-2 sm:h-[284px]",
  "col-span-6 h-36 sm:col-span-2 sm:h-[284px]",
  "col-span-12 h-48 sm:col-span-4 sm:h-[284px]",
  "col-span-6 h-36 sm:col-span-3 sm:h-[170px]",
  "col-span-6 h-36 sm:col-span-3 sm:h-[170px]",
  "col-span-6 h-36 sm:col-span-2 sm:h-[170px]",
  "col-span-6 h-36 sm:col-span-4 sm:h-[170px]",
];

const legacySections = [
  {
    semester: "spring",
    year: 2026,
    images: [
      springImg1,
      springImg2,
      springImg3,
      springImg4,
      springImg5,
      springImg6,
      springImg7,
      springImg8,
    ],
  },
  {
    semester: "fall",
    year: 2025,
    images: [
      fallImg1,
      fallImg2,
      fallImg3,
      fallImg4,
      fallImg5,
      fallImg6,
      fallImg7,
      fallImg8,
    ],
  },
];

function GalleryGrid({ title, images }) {
  return (
    <div
      className="mx-auto grid w-full max-w-[1338px] grid-cols-12 gap-4"
      data-name={`${title} Gallery`}
    >
      {images.map((image, index) => (
        <div
          key={`${title}-${index}`}
          className={`${imageLayoutClasses[index % imageLayoutClasses.length]} overflow-hidden bg-[#d9d9d9]`}
        >
          <img
            src={image}
            className="h-full w-full object-cover"
            alt={`${title} gallery photo ${index + 1}`}
            loading="lazy"
          />
        </div>
      ))}
    </div>
  );
}

function YearSection({ title, images }) {
  const [expanded, setExpanded] = useState(false);
  const hasMore = images.length > imageLayoutClasses.length;
  const visibleImages = expanded
    ? images
    : images.slice(0, imageLayoutClasses.length);

  return (
    <section className="mx-auto mt-14 w-full max-w-[1440px] px-4">
      <h2 className="mb-8 text-center text-[clamp(42px,7vw,75px)] font-bold tracking-[-1.5px] text-[#d33a02]">
        {title}
      </h2>

      <GalleryGrid title={title} images={visibleImages} />

      {hasMore && (
        <div className="mt-7 flex justify-center">
          <button
            type="button"
            className="ghostBtn"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
          >
            {expanded ? "Show less" : `Show all ${images.length} photos`}
          </button>
        </div>
      )}
    </section>
  );
}

export default function GalleryApproved() {
  const [approvedPhotos, setApprovedPhotos] = useState([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;
    getGalleryPhotos()
      .then((response) => {
        if (active) setApprovedPhotos(response.data);
      })
      .catch(() => {
        if (active) setLoadError("New gallery photos could not be loaded.");
      });
    return () => {
      active = false;
    };
  }, []);

  const gallerySections = useMemo(() => {
    const sections = new Map();

    for (const section of legacySections) {
      const key = `${section.semester}-${section.year}`;
      sections.set(key, { ...section, images: [...section.images] });
    }

    for (const photo of approvedPhotos) {
      const key = `${photo.semester}-${photo.year}`;
      const section = sections.get(key) ?? {
        semester: photo.semester,
        year: photo.year,
        images: [],
      };
      section.images.push(galleryPhotoImageUrl(photo.id));
      sections.set(key, section);
    }

    const semesterRank = { spring: 0, fall: 1 };
    return [...sections.values()]
      .sort(
        (a, b) =>
          b.year - a.year || semesterRank[b.semester] - semesterRank[a.semester],
      )
      .map((section) => ({
        ...section,
        title: gallerySectionTitle(section.semester, section.year),
      }));
  }, [approvedPhotos]);

  return (
    <section
      className="mx-auto w-full max-w-[1440px] bg-white pb-16"
      data-name="Gallery - Approved"
    >
      <GalleryUpload />

      {loadError && (
        <p className="mx-auto mt-5 max-w-[720px] px-4 text-center text-sm text-[var(--shpe-red)]">
          {loadError} The existing gallery is still available below.
        </p>
      )}

      {gallerySections.map((section) => (
        <YearSection
          key={section.title}
          title={section.title}
          images={section.images}
        />
      ))}
    </section>
  );
}
